"""
Keelway Omnichannel Messaging & Mobile Agent Dispatcher.
Enables developers worldwide to monitor, review, and approve autonomous agent tasks
via Telegram, WhatsApp, USSD/SMS fallback, and the native Keelway Mobile App.
"""

import hmac
import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional


class MessagingChannel(str, Enum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    USSD_SMS = "ussd_sms"
    MOBILE_APP = "mobile_app"


@dataclass
class ChannelPreference:
    """User preferences for remote agent notifications and review approvals."""
    user_id: str
    primary_channel: MessagingChannel
    telegram_chat_id: Optional[str] = None
    whatsapp_phone_number: Optional[str] = None
    sms_phone_number: Optional[str] = None
    mobile_device_push_token: Optional[str] = None
    allow_sms_fallback: bool = True


@dataclass
class AgentApprovalRequest:
    """Represents a pending agent action requiring human-in-the-loop signoff."""
    task_id: str
    action_type: str  # e.g., 'commit_patch', 'run_destructive_query', 'deploy_production'
    summary: str
    diff_snippet: Optional[str] = None
    timeout_seconds: int = 1800


class OmnichannelDispatcher:
    """Dispatches actionable approvals and notifications across Telegram, WhatsApp, Mobile, and SMS."""

    def __init__(self, webhook_secret: str = "KORA_OMNICHANNEL_SECRET_2026"):
        self.webhook_secret = webhook_secret
        self.pending_approvals: Dict[str, AgentApprovalRequest] = {}

    def format_telegram_payload(self, approval: AgentApprovalRequest, chat_id: str) -> Dict[str, Any]:
        """Formats an actionable Telegram Bot message with inline callback buttons."""
        text = (
            f"⚡ *Keelway Autonomous Agent Alert*\n\n"
            f"• *Task ID:* `{approval.task_id}`\n"
            f"• *Action:* `{approval.action_type}`\n"
            f"• *Summary:* {approval.summary}\n"
        )
        if approval.diff_snippet:
            text += f"\n```diff\n{approval.diff_snippet[:350]}\n```"

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✓ Approve", "callback_data": f"approve:{approval.task_id}"},
                    {"text": "✕ Reject", "callback_data": f"reject:{approval.task_id}"},
                ],
                [
                    {"text": "🔍 Inspect Full Diff", "url": f"https://keelway.dev/review/{approval.task_id}"}
                ]
            ]
        }
        return {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": keyboard,
        }

    def format_whatsapp_payload(self, approval: AgentApprovalRequest, phone_number: str) -> Dict[str, Any]:
        """Formats an interactive WhatsApp Cloud API / Twilio WhatsApp message."""
        body_text = f"⚡ Keelway Agent: {approval.summary}\nTask: {approval.task_id}\nAction: {approval.action_type}"
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text[:1024]},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": f"app_{approval.task_id}", "title": "Approve"}},
                        {"type": "reply", "reply": {"id": f"rej_{approval.task_id}", "title": "Reject"}},
                    ]
                }
            }
        }

    def format_mobile_app_payload(self, approval: AgentApprovalRequest, push_token: str) -> Dict[str, Any]:
        """Formats a push notification payload for the native Keelway Mobile App."""
        return {
            "to": push_token,
            "priority": "high",
            "notification": {
                "title": f"Agent Approval Needed: {approval.action_type}",
                "body": approval.summary,
            },
            "data": {
                "task_id": approval.task_id,
                "action_type": approval.action_type,
                "deep_link": f"keelway://task/review/{approval.task_id}",
                "requires_biometric": True,
            }
        }

    def dispatch(self, approval: AgentApprovalRequest, pref: ChannelPreference) -> Dict[str, Any]:
        """Routes notification to the user's selected primary channel with verified fallback."""
        self.pending_approvals[approval.task_id] = approval

        if pref.primary_channel == MessagingChannel.TELEGRAM and pref.telegram_chat_id:
            return {
                "channel": MessagingChannel.TELEGRAM,
                "payload": self.format_telegram_payload(approval, pref.telegram_chat_id)
            }

        elif pref.primary_channel == MessagingChannel.WHATSAPP and pref.whatsapp_phone_number:
            return {
                "channel": MessagingChannel.WHATSAPP,
                "payload": self.format_whatsapp_payload(approval, pref.whatsapp_phone_number)
            }

        elif pref.primary_channel == MessagingChannel.MOBILE_APP and pref.mobile_device_push_token:
            return {
                "channel": MessagingChannel.MOBILE_APP,
                "payload": self.format_mobile_app_payload(approval, pref.mobile_device_push_token)
            }

        elif pref.allow_sms_fallback and pref.sms_phone_number:
            # Fallback to SMS
            sms_text = f"Keelway Agent Alert: {approval.action_type} for task {approval.task_id}. Reply 1 to approve, 2 to reject."
            return {
                "channel": MessagingChannel.USSD_SMS,
                "payload": {
                    "to": pref.sms_phone_number,
                    "body": sms_text[:160]
                }
            }

        return {"channel": "none", "error": "No valid channel destination configured."}

    def handle_callback(self, task_id: str, decision: str) -> Dict[str, Any]:
        """Processes human decision: 'approve' or 'reject'."""
        approval = self.pending_approvals.pop(task_id, None)
        if not approval:
            return {"status": "error", "message": "Unknown or expired approval request"}

        approved = decision.lower() in ("approve", "1", "yes")
        return {
            "status": "success",
            "task_id": task_id,
            "action_type": approval.action_type,
            "decision": "approved" if approved else "rejected",
            "resolved_at": time.time(),
        }
