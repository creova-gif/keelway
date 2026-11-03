"""
Relay pending agent approvals to Telegram or WhatsApp and take the human's answer back.

Outbound only goes to the official Bot API / WhatsApp Cloud API hosts. While air-gapped nothing
is sent and remote answers are refused, so the approval stays in the Studio. Each message carries
a one-time nonce bound to the exact pending tool call; an answer for a call that is no longer
pending (denied, approved elsewhere, or replaced) is rejected.

Telegram uses long polling (getUpdates), so a laptop behind NAT needs no public URL.
WhatsApp replies arrive on a signed webhook (X-Hub-Signature-256), which does need one.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("keelway.messaging")

TELEGRAM_API = "https://api.telegram.org"
WHATSAPP_API = "https://graph.facebook.com/v21.0"
MAX_PENDING = 256


class RelayBlocked(RuntimeError):
    """Raised when sending is refused (air-gapped or no channel configured)."""


@dataclass
class RelayConfig:
    telegram_token: str = ""
    telegram_chat_id: str = ""
    telegram_approver_ids: List[str] = field(default_factory=list)
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_to: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = ""

    @classmethod
    def from_env(cls) -> "RelayConfig":
        env = os.environ.get
        chat = env("KEELWAY_TELEGRAM_CHAT_ID", "").strip()
        approvers = [a.strip() for a in env("KEELWAY_TELEGRAM_APPROVER_IDS", "").split(",") if a.strip()]
        return cls(
            telegram_token=env("KEELWAY_TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=chat,
            telegram_approver_ids=approvers or ([chat] if chat and not chat.startswith("-") else []),
            whatsapp_token=env("KEELWAY_WHATSAPP_TOKEN", "").strip(),
            whatsapp_phone_id=env("KEELWAY_WHATSAPP_PHONE_NUMBER_ID", "").strip(),
            whatsapp_to=env("KEELWAY_WHATSAPP_TO", "").strip().lstrip("+"),
            whatsapp_app_secret=env("KEELWAY_WHATSAPP_APP_SECRET", "").strip(),
            whatsapp_verify_token=env("KEELWAY_WHATSAPP_VERIFY_TOKEN", "").strip(),
        )

    @property
    def telegram(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)

    @property
    def telegram_buttons(self) -> bool:
        """Group chats (negative IDs) need explicit KEELWAY_TELEGRAM_APPROVER_IDS before buttons are offered."""
        return self.telegram and bool(self.telegram_approver_ids)

    @property
    def whatsapp(self) -> bool:
        return bool(self.whatsapp_token and self.whatsapp_phone_id and self.whatsapp_to)

    @property
    def whatsapp_replies(self) -> bool:
        return self.whatsapp and bool(self.whatsapp_app_secret)


def fingerprint(pending: Dict[str, Any]) -> str:
    """Stable digest of one pending tool call, so a nonce can't approve a different call."""
    return hashlib.sha256(json.dumps(pending, sort_keys=True, default=str).encode()).hexdigest()


def _summary(pending: Dict[str, Any]) -> str:
    args = pending.get("arguments") or {}
    target = args.get("path") or args.get("command") or ""
    return f"Keelway wants to run {pending.get('tool_name')} on {target}".strip()[:300]


# (nonce, approved, actor) -> human-readable outcome
DecisionHandler = Callable[[str, bool, str], Awaitable[str]]


class ApprovalRelay:
    def __init__(
        self,
        config: Optional[RelayConfig] = None,
        air_gapped: Callable[[], bool] = lambda: False,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.config = config or RelayConfig.from_env()
        self.air_gapped = air_gapped
        self.transport = transport
        self.on_decision: Optional[DecisionHandler] = None
        self._pending: Dict[str, Tuple[str, str]] = {}
        self._telegram_offset = 0

    def channels(self) -> List[str]:
        return [name for name, on in (("telegram", self.config.telegram), ("whatsapp", self.config.whatsapp)) if on]

    def _client(self, timeout: float = 15.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self.transport)

    def _check_can_send(self) -> None:
        if self.air_gapped():
            raise RelayBlocked("Air-gapped: messaging is blocked, nothing left this machine.")
        if not self.channels():
            raise RelayBlocked("No messaging channel is configured.")

    def claim(self, nonce: str) -> Optional[Tuple[str, str]]:
        """One-time: returns (task_id, fingerprint) and forgets the nonce."""
        return self._pending.pop(nonce, None)

    def forget_task(self, task_id: str) -> None:
        """Invalidate outstanding buttons for a task once its approval is answered anywhere."""
        for old, (tid, _) in list(self._pending.items()):
            if tid == task_id:
                del self._pending[old]

    def _new_nonce(self, task_id: str, pending: Dict[str, Any]) -> str:
        self.forget_task(task_id)
        while len(self._pending) >= MAX_PENDING:
            del self._pending[next(iter(self._pending))]
        nonce = secrets.token_urlsafe(12)
        self._pending[nonce] = (task_id, fingerprint(pending))
        return nonce

    async def notify_pending(self, pending: Dict[str, Any]) -> Dict[str, Any]:
        """Send one approval request with Approve/Deny buttons to every configured channel."""
        self._check_can_send()
        nonce = self._new_nonce(pending["task_id"], pending)
        text = f"{_summary(pending)}\nTask: {pending['task_id']}"
        return {"sent": await self._send_all(text, nonce)}

    async def send_test(self) -> Dict[str, Any]:
        self._check_can_send()
        return {"sent": await self._send_all("Keelway: messaging works. Approval requests will arrive here.", None)}

    async def _send_all(self, text: str, nonce: Optional[str]) -> Dict[str, Any]:
        """One channel failing (timeout, DNS, 5xx) never stops the others."""
        senders = []
        if self.config.telegram:
            senders.append(("telegram", self._telegram_send))
        if self.config.whatsapp:
            senders.append(("whatsapp", self._whatsapp_send))
        results: Dict[str, Any] = {}
        async with self._client() as client:
            for name, send in senders:
                try:
                    results[name] = await send(client, text, nonce)
                except Exception as e:
                    logger.warning("%s send failed: %s", name, type(e).__name__)
                    results[name] = {"ok": False, "error": type(e).__name__}
        return results

    async def _telegram_send(self, client: httpx.AsyncClient, text: str, nonce: Optional[str]) -> Dict[str, Any]:
        body: Dict[str, Any] = {"chat_id": self.config.telegram_chat_id, "text": text}
        if nonce and self.config.telegram_buttons:
            body["reply_markup"] = {"inline_keyboard": [[
                {"text": "Approve", "callback_data": f"kw:a:{nonce}"},
                {"text": "Deny", "callback_data": f"kw:d:{nonce}"},
            ]]}
        r = await client.post(f"{TELEGRAM_API}/bot{self.config.telegram_token}/sendMessage", json=body)
        return {"ok": r.status_code == 200 and r.json().get("ok", False), "status": r.status_code}

    async def _whatsapp_send(self, client: httpx.AsyncClient, text: str, nonce: Optional[str]) -> Dict[str, Any]:
        body: Dict[str, Any] = {"messaging_product": "whatsapp", "to": self.config.whatsapp_to}
        if nonce and self.config.whatsapp_replies:
            body.update(type="interactive", interactive={
                "type": "button",
                "body": {"text": text[:1024]},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": f"kw:a:{nonce}", "title": "Approve"}},
                    {"type": "reply", "reply": {"id": f"kw:d:{nonce}", "title": "Deny"}},
                ]},
            })
        else:
            body.update(type="text", text={"body": text[:4096]})
        r = await client.post(
            f"{WHATSAPP_API}/{self.config.whatsapp_phone_id}/messages",
            json=body,
            headers={"Authorization": f"Bearer {self.config.whatsapp_token}"},
        )
        return {"ok": r.status_code == 200, "status": r.status_code}

    async def _decide(self, data: str, actor: str) -> str:
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "kw" or parts[1] not in ("a", "d"):
            return "Unknown button."
        if self.air_gapped():
            return "Keelway is air-gapped: answer in the Studio."
        if not self.on_decision:
            return "Keelway is not accepting remote answers."
        return await self.on_decision(parts[2], parts[1] == "a", actor)

    # Telegram: long polling, no public URL needed.

    async def poll_telegram_once(self, timeout: int = 25) -> int:
        """Fetch and handle one batch of button presses; returns how many were handled."""
        if not self.config.telegram or self.air_gapped():
            return 0
        base = f"{TELEGRAM_API}/bot{self.config.telegram_token}"
        handled = 0
        async with self._client(timeout + 10) as client:
            r = await client.post(f"{base}/getUpdates", json={
                "offset": self._telegram_offset, "timeout": timeout, "allowed_updates": ["callback_query"],
            })
            for update in r.json().get("result", []) if r.status_code == 200 else []:
                self._telegram_offset = max(self._telegram_offset, int(update.get("update_id", 0)) + 1)
                cq = update.get("callback_query") or {}
                sender = str((cq.get("from") or {}).get("id", ""))
                chat = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
                if chat != self.config.telegram_chat_id or sender not in self.config.telegram_approver_ids:
                    outcome = "You are not an approver for this Keelway workspace."
                else:
                    try:
                        outcome = await self._decide(str(cq.get("data", "")), f"telegram:{sender}")
                    except Exception as e:
                        logger.warning("Telegram decision failed: %s", type(e).__name__)
                        outcome = "Keelway could not apply that answer. Use the Studio."
                    handled += 1
                if cq.get("id"):
                    await client.post(f"{base}/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": outcome[:200]})
        return handled

    async def run_telegram_poller(self) -> None:
        while True:
            try:
                if self.air_gapped() or not self.config.telegram:
                    await asyncio.sleep(5)
                elif await self.poll_telegram_once() == 0:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # network drops are normal offline; keep polling
                logger.warning("Telegram poll failed: %s", type(e).__name__)
                await asyncio.sleep(10)

    # WhatsApp: signed webhook.

    def whatsapp_signature_ok(self, raw_body: bytes, header: Optional[str]) -> bool:
        if not self.config.whatsapp_app_secret or not header or not header.startswith("sha256="):
            return False
        want = hmac.new(self.config.whatsapp_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(want, header[len("sha256="):])

    async def handle_whatsapp(self, payload: Dict[str, Any]) -> List[str]:
        outcomes = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                for msg in (change.get("value") or {}).get("messages", []):
                    reply = ((msg.get("interactive") or {}).get("button_reply") or {})
                    if not reply:
                        continue
                    sender = str(msg.get("from", "")).lstrip("+")
                    if sender != self.config.whatsapp_to:
                        outcomes.append("not an approver")
                        continue
                    outcomes.append(await self._decide(str(reply.get("id", "")), f"whatsapp:{sender}"))
        return outcomes
