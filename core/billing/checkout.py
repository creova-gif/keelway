"""Provider-neutral checkout: a verified payment event becomes a signed licence.

This runs only on Sorvex Labs' issuing server, because it holds the Ed25519 signing key. Customer machines
never run it; they install the licence file it produces (`keelway entitlements install`).

A payment provider (Paddle, Lemon Squeezy, ...) plugs in as an adapter that verifies the provider's webhook
signature and turns its payload into a `PaymentEvent`. `SignedWebhookAdapter` is the built-in adapter: a
timestamped HMAC-SHA256 over the raw body, suitable for a relay you control and for tests.

Offline licences cannot be recalled. A refund or cancellation stops renewals and is recorded in the ledger;
the licence already issued keeps working until it expires, which is why plans are issued for short periods.
"""

import hashlib
import hmac
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.billing.entitlements import EntitlementCertificate, LicenseTier
from keelway.security.source_defaults import InsecureDefaultConfiguration, is_source_default

WEBHOOK_SECRET_ENV = "KEELWAY_CHECKOUT_WEBHOOK_SECRET"
SIGNATURE_HEADER = "x-keelway-signature"
TIMESTAMP_HEADER = "x-keelway-timestamp"
SIGNATURE_TOLERANCE_SECONDS = 300
EVENT_KINDS = ("paid", "refunded", "cancelled")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class Plan:
    tier: LicenseTier
    seats: int
    days: int
    features: tuple = ()


PLANS: Dict[str, Plan] = {
    "pro-monthly": Plan(LicenseTier.PRO, seats=1, days=31),
    "pro-yearly": Plan(LicenseTier.PRO, seats=1, days=366),
    "team-monthly": Plan(LicenseTier.PRO, seats=5, days=31),
    "enterprise-yearly": Plan(LicenseTier.ENTERPRISE, seats=25, days=366),
}


@dataclass
class PaymentEvent:
    event_id: str
    kind: str
    order_id: str
    plan: str = ""
    org_id: str = ""
    org_name: str = ""
    email: str = ""
    seats: int = 0


class WebhookRejected(ValueError):
    """The request is not a genuine, well-formed payment event."""


class ProviderAdapter(Protocol):
    name: str

    def verify(self, body: bytes, headers: Mapping[str, str], now: Optional[float] = None) -> None: ...

    def parse(self, body: bytes) -> PaymentEvent: ...


def _require_secret(secret: str) -> bytes:
    if not secret or len(secret) < 32 or is_source_default(secret):
        raise InsecureDefaultConfiguration(
            f"checkout webhook secret must be set explicitly ({WEBHOOK_SECRET_ENV}, at least 32 characters)"
        )
    return secret.encode("utf-8")


def sign_webhook(secret: str, body: bytes, timestamp: int) -> str:
    mac = hmac.new(secret.encode("utf-8"), str(timestamp).encode("ascii") + b"." + body, hashlib.sha256)
    return "v1=" + mac.hexdigest()


class SignedWebhookAdapter:
    """`X-Keelway-Timestamp: <unix>` and `X-Keelway-Signature: v1=<hex HMAC-SHA256(secret, ts + "." + body)>`."""

    name = "keelway"

    def __init__(self, secret: str):
        self._secret = _require_secret(secret).decode("utf-8")

    def verify(self, body: bytes, headers: Mapping[str, str], now: Optional[float] = None) -> None:
        lower = {k.lower(): v for k, v in headers.items()}
        ts, sig = lower.get(TIMESTAMP_HEADER, ""), lower.get(SIGNATURE_HEADER, "")
        if not ts.isdigit() or not sig:
            raise WebhookRejected("missing signature")
        if abs((now if now is not None else time.time()) - int(ts)) > SIGNATURE_TOLERANCE_SECONDS:
            raise WebhookRejected("stale or future timestamp")
        if not hmac.compare_digest(sign_webhook(self._secret, body, int(ts)), sig):
            raise WebhookRejected("invalid signature")

    def parse(self, body: bytes) -> PaymentEvent:
        try:
            data = json.loads(body)
            event = PaymentEvent(
                event_id=str(data["id"]), kind=str(data["type"]), order_id=str(data["order_id"]),
                plan=str(data.get("plan", "")), org_id=str(data.get("org_id", "")),
                org_name=str(data.get("org_name", "")), email=str(data.get("email", "")),
                seats=int(data.get("seats", 0)),
            )
        except (ValueError, KeyError, TypeError) as e:
            raise WebhookRejected(f"malformed event: {e}") from e
        return event


class LicenceIssuer:
    """Turns payment events into signed licences, once per event, with a persistent ledger."""

    def __init__(
        self,
        private_key: Ed25519PrivateKey,
        key_id: str,
        ledger_path: Path,
        outbox: Path,
        plans: Optional[Dict[str, Plan]] = None,
        deliver: Optional[Callable[[Dict[str, Any], EntitlementCertificate, Path], None]] = None,
    ):
        self.private_key, self.key_id = private_key, key_id
        self.ledger_path, self.outbox = Path(ledger_path), Path(outbox)
        self.plans = PLANS if plans is None else plans
        self.deliver = deliver
        self._lock = threading.Lock()
        self._ledger = self._read_ledger()

    def _read_ledger(self) -> Dict[str, Any]:
        if self.ledger_path.exists():
            return json.loads(self.ledger_path.read_text(encoding="utf-8"))
        return {"events": [], "orders": {}}

    def _write_ledger(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ledger_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._ledger, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.ledger_path)

    def order(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self._ledger["orders"].get(order_id)

    def handle(self, event: PaymentEvent, now: Optional[float] = None) -> Dict[str, Any]:
        if event.kind not in EVENT_KINDS:
            return {"status": "ignored", "reason": f"event type {event.kind!r} is not handled"}
        for label, value in (("event id", event.event_id), ("order id", event.order_id)):
            if not _SAFE_ID.match(value):
                raise WebhookRejected(f"invalid {label}")
        with self._lock:
            if event.event_id in self._ledger["events"]:
                return {"status": "duplicate", "order_id": event.order_id}
            result = self._paid(event, now) if event.kind == "paid" else self._ended(event)
            self._ledger["events"].append(event.event_id)
            self._write_ledger()
            return result

    def _ended(self, event: PaymentEvent) -> Dict[str, Any]:
        order = self._ledger["orders"].get(event.order_id)
        if order is None:
            return {"status": "ignored", "reason": "unknown order", "order_id": event.order_id}
        order["status"] = event.kind
        return {"status": event.kind, "order_id": event.order_id, "licence_valid_until": order["expires_at"]}

    def _paid(self, event: PaymentEvent, now: Optional[float]) -> Dict[str, Any]:
        order = self._ledger["orders"].get(event.order_id)
        if order is not None and order["status"] != "active":
            return {"status": "refused", "reason": f"order is {order['status']}", "order_id": event.order_id}
        plan_id = order["plan"] if order else event.plan
        plan = self.plans.get(plan_id)
        if plan is None:
            raise WebhookRejected(f"unknown plan {plan_id!r}")
        org_id = order["org_id"] if order else (event.org_id or event.order_id)
        if not _SAFE_ID.match(org_id):
            raise WebhookRejected("invalid org id")
        current = now if now is not None else time.time()
        start = max(current, order["expires_at"]) if order else current
        cert = EntitlementCertificate(
            org_id=org_id, org_name=event.org_name or (order or {}).get("org_name") or org_id, tier=plan.tier,
            seats=max(plan.seats, event.seats), allowed_features=sorted(plan.features), issued_at=current,
            expires_at=start + plan.days * 86400,
        )
        cert.sign(self.private_key, self.key_id)
        self.outbox.mkdir(parents=True, exist_ok=True)
        path = self.outbox / f"{event.order_id}-{event.event_id}.json"
        path.write_text(json.dumps(cert.to_dict(), indent=2) + "\n", encoding="utf-8")
        record = {
            "status": "active", "plan": plan_id, "org_id": org_id, "org_name": cert.org_name,
            "email": event.email or (order or {}).get("email", ""), "seats": cert.seats,
            "expires_at": cert.expires_at, "licence_file": path.name,
        }
        self._ledger["orders"][event.order_id] = record
        if self.deliver:
            self.deliver(record, cert, path)
        return {"status": "renewed" if order else "issued", "order_id": event.order_id,
                "expires_at": cert.expires_at, "licence_file": path.name}


def create_issuer_app(issuer: LicenceIssuer, adapters: List[ProviderAdapter]):
    """FastAPI app with POST /v1/checkout/webhook/{provider}. Run it on the issuing server, not with Keelway."""
    from fastapi import FastAPI, HTTPException, Request

    by_name = {a.name: a for a in adapters}
    app = FastAPI(title="Keelway licence issuer", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    def healthz() -> Dict[str, Any]:
        return {"ok": True, "providers": sorted(by_name)}

    @app.post("/v1/checkout/webhook/{provider}")
    async def webhook(provider: str, request: Request) -> Dict[str, Any]:
        adapter = by_name.get(provider)
        if adapter is None:
            raise HTTPException(404, "unknown provider")
        body = await request.body()
        try:
            adapter.verify(body, request.headers)
        except WebhookRejected as e:
            raise HTTPException(401, str(e)) from e
        try:
            return issuer.handle(adapter.parse(body))
        except WebhookRejected as e:
            raise HTTPException(422, str(e)) from e

    return app


__all__ = [
    "PLANS", "Plan", "PaymentEvent", "WebhookRejected", "SignedWebhookAdapter", "LicenceIssuer",
    "create_issuer_app", "sign_webhook", "WEBHOOK_SECRET_ENV",
]
