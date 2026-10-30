"""
Standard library unit tests for Kora AI Global Sovereign Multi-Rail Payment Broker.
Runs in clean zero-dependency environments.
"""

import unittest
from core.storage.payment_broker import GlobalPaymentBroker, GlobalRail


class TestGlobalPaymentBroker(unittest.TestCase):
    def setUp(self):
        self.broker = GlobalPaymentBroker()

    def test_mpesa_daraja_intent_creation(self):
        intent = self.broker.create_intent(
            rail=GlobalRail.MPESA,
            amount=500.0,
            currency="KES",
            recipient="254712345678",
            description="Model compute hours"
        )
        self.assertEqual(intent.status, "pending")
        self.assertEqual(intent.rail, GlobalRail.MPESA)
        self.assertEqual(intent.payment_payload["provider"], "Safaricom_Daraja")
        self.assertEqual(intent.payment_payload["phone_number"], "254712345678")
        self.assertEqual(intent.payment_payload["amount"], 500)

    def test_pix_copia_e_cola_intent(self):
        intent = self.broker.create_intent(
            rail=GlobalRail.PIX,
            amount=25.50,
            currency="BRL",
            recipient="developer@kora.ai",
            description="Agent worktree execution"
        )
        self.assertEqual(intent.rail, GlobalRail.PIX)
        self.assertIn("br.gov.bcb.pix", intent.payment_payload["copia_e_cola"])
        self.assertEqual(intent.payment_payload["pix_key"], "developer@kora.ai")

    def test_upi_intent_url(self):
        intent = self.broker.create_intent(
            rail=GlobalRail.UPI,
            amount=150.00,
            currency="INR",
            recipient="kora-agent@okaxis",
            description="Local AST repair token"
        )
        self.assertEqual(intent.rail, GlobalRail.UPI)
        self.assertIn("upi://pay?pa=kora-agent@okaxis", intent.payment_payload["intent_url"])
        self.assertEqual(intent.payment_payload["vpa"], "kora-agent@okaxis")

    def test_lightning_l402_and_macaroon(self):
        intent = self.broker.create_intent(
            rail=GlobalRail.LIGHTNING_L402,
            amount=1000.0,
            currency="SATS",
            recipient="03abcdef...pubkey",
            description="Streaming API inference"
        )
        self.assertEqual(intent.rail, GlobalRail.LIGHTNING_L402)
        self.assertIn("macaroon", intent.payment_payload)
        self.assertIn("L402", intent.payment_payload["challenge_header"])

        verified = self.broker.verify_settlement(intent.intent_id, settlement_proof="f90a82b874cd2901aa")
        self.assertTrue(verified)
        self.assertEqual(intent.status, "settled")

    def test_offline_voucher_settlement(self):
        intent = self.broker.create_intent(
            rail=GlobalRail.OFFLINE_VOUCHER,
            amount=50.0,
            currency="USD",
            recipient="auditor_airgap_node_1",
            description="Prepaid SCIF compute voucher"
        )
        self.assertEqual(intent.rail, GlobalRail.OFFLINE_VOUCHER)
        voucher_code = intent.payment_payload["voucher_code"]
        self.assertTrue(voucher_code.startswith("VOUCH-"))

        self.assertFalse(self.broker.verify_settlement(intent.intent_id, "WRONG-CODE"))
        self.assertEqual(intent.status, "pending")

        self.assertTrue(self.broker.verify_settlement(intent.intent_id, voucher_code))
        self.assertEqual(intent.status, "settled")


if __name__ == "__main__":
    unittest.main()
