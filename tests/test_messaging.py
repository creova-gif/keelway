"""
Standard library unit tests for Keelway Omnichannel Messaging & Mobile Agent Dispatcher.
"""

import unittest
from core.api.messaging import (
    OmnichannelDispatcher,
    MessagingChannel,
    ChannelPreference,
    AgentApprovalRequest,
)


class TestOmnichannelMessaging(unittest.TestCase):
    def setUp(self):
        self.dispatcher = OmnichannelDispatcher()
        self.approval = AgentApprovalRequest(
            task_id="task_99a",
            action_type="commit_patch",
            summary="Auto-repaired 2 failing pytest cases in auth.py",
            diff_snippet="+ def verify_token(): return True",
        )

    def test_telegram_formatting(self):
        payload = self.dispatcher.format_telegram_payload(self.approval, chat_id="123456789")
        self.assertEqual(payload["chat_id"], "123456789")
        self.assertIn("task_99a", payload["text"])
        self.assertIn("Auto-repaired 2 failing pytest cases", payload["text"])
        buttons = payload["reply_markup"]["inline_keyboard"][0]
        self.assertEqual(buttons[0]["callback_data"], "approve:task_99a")
        self.assertEqual(buttons[1]["callback_data"], "reject:task_99a")

    def test_whatsapp_formatting(self):
        payload = self.dispatcher.format_whatsapp_payload(self.approval, phone_number="254712345678")
        self.assertEqual(payload["messaging_product"], "whatsapp")
        self.assertEqual(payload["to"], "254712345678")
        interactive = payload["interactive"]
        self.assertEqual(interactive["type"], "button")
        self.assertEqual(interactive["action"]["buttons"][0]["reply"]["title"], "Approve")

    def test_mobile_app_formatting(self):
        payload = self.dispatcher.format_mobile_app_payload(self.approval, push_token="push_xyz789")
        self.assertEqual(payload["to"], "push_xyz789")
        self.assertEqual(payload["data"]["deep_link"], "keelway://task/review/task_99a")
        self.assertTrue(payload["data"]["requires_biometric"])

    def test_dispatch_preferences(self):
        # 1. Telegram preference
        tg_pref = ChannelPreference(
            user_id="user_1",
            primary_channel=MessagingChannel.TELEGRAM,
            telegram_chat_id="tg_123",
        )
        res_tg = self.dispatcher.dispatch(self.approval, tg_pref)
        self.assertEqual(res_tg["channel"], MessagingChannel.TELEGRAM)

        # 2. WhatsApp preference
        wa_pref = ChannelPreference(
            user_id="user_2",
            primary_channel=MessagingChannel.WHATSAPP,
            whatsapp_phone_number="5511999998888",
        )
        res_wa = self.dispatcher.dispatch(self.approval, wa_pref)
        self.assertEqual(res_wa["channel"], MessagingChannel.WHATSAPP)

        # 3. SMS Fallback when primary has no credentials
        sms_pref = ChannelPreference(
            user_id="user_3",
            primary_channel=MessagingChannel.TELEGRAM,
            telegram_chat_id=None,
            sms_phone_number="+254700000000",
            allow_sms_fallback=True,
        )
        res_sms = self.dispatcher.dispatch(self.approval, sms_pref)
        self.assertEqual(res_sms["channel"], MessagingChannel.USSD_SMS)

    def test_callback_approval_and_rejection(self):
        self.dispatcher.pending_approvals["task_abc"] = self.approval
        res_approve = self.dispatcher.handle_callback("task_abc", "approve")
        self.assertEqual(res_approve["status"], "success")
        self.assertEqual(res_approve["decision"], "approved")

        self.dispatcher.pending_approvals["task_def"] = self.approval
        res_reject = self.dispatcher.handle_callback("task_def", "reject")
        self.assertEqual(res_reject["status"], "success")
        self.assertEqual(res_reject["decision"], "rejected")


if __name__ == "__main__":
    unittest.main()
