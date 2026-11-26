"""
Keelway Ultra-Low-Bandwidth Telephony & Signaling Adapter (USSD / SMS).
Enables AI agent interaction across emerging markets on 2G feature phones
via Africa's Talking, Twilio, or generic telecom signaling gateways.
"""

from typing import Dict, Any, Tuple


class TelephonyAdapter:
    """Handles USSD session lifecycle, character-budget compression, and SMS asynchronous fallback."""

    MAX_USSD_CHARS = 180
    MAX_SMS_CHARS = 160

    @classmethod
    def format_ussd_response(cls, message: str, is_terminal: bool = False) -> str:
        """
        Formats response string according to telecom protocol:
        - CON: Continues session, prompts user for next input
        - END: Terminates session, outputs final message
        """
        prefix = "END " if is_terminal else "CON "
        compressed = message.strip()
        if len(compressed) > cls.MAX_USSD_CHARS:
            compressed = compressed[: cls.MAX_USSD_CHARS - 3] + "..."
        return f"{prefix}{compressed}"

    @classmethod
    def parse_africastalking_request(cls, form_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Parses standard Africa's Talking / Twilio USSD webhook payload:
        - sessionId: Unique string identifying the active session
        - serviceCode: Shortcode dialed (e.g. *384#)
        - phoneNumber: MSISDN of the caller (e.g. +254712345678)
        - text: Accumulated user inputs separated by '*' (e.g. '1*2')
        """
        session_id = form_data.get("sessionId", "")
        phone_number = form_data.get("phoneNumber", "")
        raw_text = form_data.get("text", "").strip()

        steps = [s for s in raw_text.split("*") if s] if raw_text else []
        latest_input = steps[-1] if steps else ""

        return {
            "session_id": session_id,
            "phone_number": phone_number,
            "steps": steps,
            "latest_input": latest_input,
            "depth": len(steps),
        }

    @classmethod
    def generate_menu_response(cls, depth: int, user_input: str) -> Tuple[str, bool]:
        """
        Generates deterministic lightweight menu navigation for 2G users:
        - Level 0: Main Menu
        - Level 1: Feature selection (1: Ask Keelway, 2: System Status, 3: Voucher Balance)
        """
        if depth == 0 or not user_input:
            menu = (
                "Welcome to Keelway Sovereign Agent\n"
                "1. Ask Question\n"
                "2. System Status\n"
                "3. Token Balance"
            )
            return cls.format_ussd_response(menu, is_terminal=False), False

        elif depth == 1:
            if user_input == "1":
                return cls.format_ussd_response("Type your prompt / question:", is_terminal=False), False
            elif user_input == "2":
                status_msg = "Keelway Core: ACTIVE\nEdge Model: Qwen 3.5\nAir-Gap: ZERO-EGRESS"
                return cls.format_ussd_response(status_msg, is_terminal=True), True
            elif user_input == "3":
                balance_msg = "Balance: 500,000 tokens ($0.00)\nVoucher Rail: ACTIVE"
                return cls.format_ussd_response(balance_msg, is_terminal=True), True
            else:
                return cls.format_ussd_response("Invalid option. Session ended.", is_terminal=True), True

        # Prompt submitted at depth 2
        return cls.format_ussd_response(f"Keelway Answer: Query '{user_input[:20]}' processed locally.", is_terminal=True), True
