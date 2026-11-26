from core.storage.ap2 import AgentPaymentGateway, PaymentRail
from core.security.rbac import AccessControlManager, Role, Permission


def test_ap2_mandate_issuance_and_validation():
    gateway = AgentPaymentGateway()
    mandate = gateway.issue_mandate(user_id="user_justin", max_amount_cents=500, duration_seconds=3600)

    # Valid microtransaction (50 cents)
    assert mandate.is_valid(amount_cents=50, rail=PaymentRail.HTTP_402_MICRO) is True

    # Exceeds cap (600 cents > 500 cents limit)
    assert mandate.is_valid(amount_cents=600, rail=PaymentRail.HTTP_402_MICRO) is False


def test_ap2_http_402_challenge_handling():
    gateway = AgentPaymentGateway()
    mandate = gateway.issue_mandate(user_id="user_justin", max_amount_cents=200)

    headers = {
        "x-payment-amount-cents": "10",
        "x-payment-destination": "research-database-node",
    }
    result = gateway.handle_http_402_challenge(status_code=402, challenge_headers=headers, mandate=mandate)
    assert result["status"] == "authorized"
    assert "Bearer ap2_" in result["auth_header"]
    assert result["amount_cents"] == 10
    assert len(gateway.ledger) == 1

    # Over-budget challenge
    excessive_headers = {"x-payment-amount-cents": "500"}
    denied = gateway.handle_http_402_challenge(status_code=402, challenge_headers=excessive_headers, mandate=mandate)
    assert denied["status"] == "denied"


def test_rbac_permissions_and_audit():
    # Engineer cannot approve Tier 3 sandboxes
    assert AccessControlManager.can_perform(Role.ENGINEER, Permission.APPROVE_TIER3) is False
    # Admin can approve Tier 3
    assert AccessControlManager.can_perform(Role.ADMIN, Permission.APPROVE_TIER3) is True
    # Auditor is strictly read-only
    assert AccessControlManager.can_perform(Role.AUDITOR, Permission.EXECUTE_AGENT) is False
    assert AccessControlManager.can_perform(Role.AUDITOR, Permission.VIEW_AUDIT_LOGS) is True

    # Audit log generation
    audit = AccessControlManager.audit_event(
        actor_id="eng_01",
        role=Role.ENGINEER,
        action="approve_tier3",
        resource="sandbox_eval",
        allowed=False,
    )
    assert audit["allowed"] is False
    assert len(audit["entry_hash"]) == 64
