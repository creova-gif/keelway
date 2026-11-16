"""Provider-neutral checkout: verified payment webhooks issue, renew and end licences exactly once."""

import json
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from core.billing.checkout import (
    LicenceIssuer, PaymentEvent, SignedWebhookAdapter, WebhookRejected, create_issuer_app, sign_webhook,
)
from core.billing.entitlements import EntitlementCertificate, EntitlementManager, LicenseTier, public_key_text
from keelway.security.source_defaults import InsecureDefaultConfiguration

SECRET = "checkout-test-secret-0123456789abcdef"
SIGNER = Ed25519PrivateKey.generate()
TRUSTED = {"k1": public_key_text(SIGNER)}


@pytest.fixture
def issuer(tmp_path):
    return LicenceIssuer(SIGNER, "k1", tmp_path / "ledger.json", tmp_path / "out")


def _paid(event_id="evt_1", order_id="ord_1", plan="pro-monthly", **kw):
    return PaymentEvent(event_id=event_id, kind="paid", order_id=order_id, plan=plan, org_id="acme",
                        email="dev@acme.test", **kw)


def _licence(issuer, result):
    return EntitlementCertificate.from_dict(json.loads((issuer.outbox / result["licence_file"]).read_text()))


def test_payment_issues_a_licence_the_customer_can_install(issuer, tmp_path):
    result = issuer.handle(_paid())
    assert result["status"] == "issued"
    cert = _licence(issuer, result)
    assert (cert.tier, cert.seats, cert.org_id) == (LicenseTier.PRO, 1, "acme")
    assert cert.expires_at - cert.issued_at == 31 * 86400
    mgr = EntitlementManager(storage_path=tmp_path / "customer.json", trusted_keys=TRUSTED)
    assert mgr.register_certificate(cert) == (True, "ACTIVE")


def test_same_event_twice_issues_once_even_after_restart(issuer, tmp_path):
    issuer.handle(_paid())
    assert issuer.handle(_paid())["status"] == "duplicate"
    again = LicenceIssuer(SIGNER, "k1", tmp_path / "ledger.json", tmp_path / "out")
    assert again.handle(_paid())["status"] == "duplicate"
    assert len(list((tmp_path / "out").iterdir())) == 1


def test_renewal_extends_from_the_current_expiry(issuer):
    now = time.time()
    first = issuer.handle(_paid(), now=now)
    second = issuer.handle(_paid(event_id="evt_2", plan=""), now=now + 86400)
    assert second["status"] == "renewed"
    assert second["expires_at"] == pytest.approx(first["expires_at"] + 31 * 86400)
    assert _licence(issuer, second).tier == LicenseTier.PRO


def test_refund_stops_renewals_but_cannot_recall_the_offline_licence(issuer):
    first = issuer.handle(_paid())
    ended = issuer.handle(PaymentEvent(event_id="evt_r", kind="refunded", order_id="ord_1"))
    assert ended == {"status": "refunded", "order_id": "ord_1", "licence_valid_until": first["expires_at"]}
    assert issuer.handle(_paid(event_id="evt_3"))["status"] == "refused"
    assert issuer.order("ord_1")["status"] == "refunded"


def test_unknown_plan_and_unsafe_ids_are_rejected_and_can_be_retried(issuer):
    with pytest.raises(WebhookRejected):
        issuer.handle(_paid(plan="free-forever"))
    with pytest.raises(WebhookRejected):
        issuer.handle(_paid(event_id="evt_x", order_id="../../etc"))
    assert issuer.handle(_paid())["status"] == "issued"


def test_seats_can_be_raised_but_not_below_the_plan(issuer):
    assert _licence(issuer, issuer.handle(_paid(plan="team-monthly", seats=12))).seats == 12
    assert _licence(issuer, issuer.handle(_paid("evt_2", "ord_2", plan="team-monthly", seats=1))).seats == 5


def test_webhook_secret_must_be_explicit():
    for bad in ("", "short", "KEELWAY_BILLING_WEBHOOK_SECRET_2026"):
        with pytest.raises(InsecureDefaultConfiguration):
            SignedWebhookAdapter(bad)


def _post(client, payload, secret=SECRET, ts=None, path="/v1/checkout/webhook/keelway"):
    body = json.dumps(payload).encode()
    ts = int(time.time()) if ts is None else ts
    headers = {"X-Keelway-Timestamp": str(ts), "X-Keelway-Signature": sign_webhook(secret, body, ts)}
    return client.post(path, content=body, headers=headers)


def test_http_webhook_end_to_end(issuer):
    client = TestClient(create_issuer_app(issuer, [SignedWebhookAdapter(SECRET)]))
    event = {"id": "evt_1", "type": "paid", "order_id": "ord_1", "plan": "enterprise-yearly", "org_id": "acme"}
    ok = _post(client, event)
    assert ok.status_code == 200 and ok.json()["status"] == "issued"
    assert _post(client, event).json()["status"] == "duplicate"
    assert _post(client, event, secret="x" * 40).status_code == 401
    assert _post(client, event, ts=int(time.time()) - 3600).status_code == 401
    assert client.post("/v1/checkout/webhook/keelway", content=b"{}").status_code == 401
    assert _post(client, {"id": "evt_9"}).status_code == 422
    assert _post(client, event, path="/v1/checkout/webhook/nope").status_code == 404
    assert _post(client, {"id": "e5", "type": "subscription.paused", "order_id": "o"}).json()["status"] == "ignored"
