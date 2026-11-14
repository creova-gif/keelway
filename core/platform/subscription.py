"""
Keelway 5-Stream Subscription, BYOM Compliance, Quota Fair-Use & Model License Policy Engine.

Models the five canonical access and monetization streams:
1. `community` — Free / Community Tier ($0, open-core local platform, $0.00/tok local hardware, fair-use quotas)
2. `pro` — Keelway Pro ($39/seat/mo annual, $49 monthly, multi-agent orchestration, higher limits)
3. `byom` — Bring Your Own Model (authorized OpenAI/Anthropic/Gemini/self-hosted vLLM API credentials;
   platform bills separately for orchestration, workspace, and automation execution)
4. `enterprise` — Keelway Enterprise (dedicated VPC/on-prem, RBAC, retention policies, auditability, SLAs)
5. `marketplace` — Marketplace creator/platform revenue-share accounting

Enforces a hard fail-closed compliance guard (`validate_byom_credential`) ensuring consumer web
subscriptions (ChatGPT Plus/Pro/Team web, Claude Pro/Max web, session cookies, unofficial tokens)
are NEVER assumed to grant third-party API access.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any, Dict, List, Optional

try:
    from core.billing.entitlements import LicenseTier
except ImportError:
    class LicenseTier(str, Enum):  # type: ignore[no-redef]
        COMMUNITY = "community"
        PRO = "pro"
        ENTERPRISE = "enterprise"

SUPPORTED_BYOM_PROVIDERS = {"openai", "anthropic", "gemini", "self_hosted_vllm"}
AUTHORIZED_BYOM_KINDS = {"api_key", "official_integration"}

_CONSUMER_TOKEN_PATTERNS = (
    re.compile(r"(?i)^sk-ant-sid"),
    re.compile(r"(?i)^chatgpt-(?:session|plus|pro|team|web)"),
    re.compile(r"(?i)^claude-(?:web|pro|max)-?cookie"),
    re.compile(r"(?i)(?:session[_-]?cookie|__secure-next-auth|web-session-token)"),
    re.compile(r"(?i)^(?:cookie|sid)="),
)

MARKETPLACE_SPLITS: Dict[str, Dict[str, int]] = {
    "first_party": {"creator_share_pct": 0, "platform_share_pct": 100},
    "verified_third_party": {"creator_share_pct": 85, "platform_share_pct": 15},
    "enterprise_partner": {"creator_share_pct": 80, "platform_share_pct": 20},
}

SUBSCRIPTION_TIERS: Dict[str, Dict[str, Any]] = {
    LicenseTier.COMMUNITY.value: {
        "id": "community",
        "name": "Free / Community",
        "stream_kind": "open_core_community",
        "monthly_price_usd": 0,
        "annual_monthly_price_usd": 0,
        "local_hardware_token_cost_usd": 0.0,
        "daily_open_weight_tokens": 150_000,
        "rpm_limit": 20,
        "max_concurrent_agents": 2,
        "max_active_workflows": 3,
        "fair_use_enforced": True,
        "capabilities": [
            "open_core_local_platform",
            "unlimited_local_hardware_inference",
            "community_open_weight_pool",
            "core_dev_tools",
            "basic_automation",
            "p10_human_approval_gates",
        ],
    },
    LicenseTier.PRO.value: {
        "id": "pro",
        "name": "Keelway Pro",
        "stream_kind": "saas_seat_subscription",
        "monthly_price_usd": 49,
        "annual_monthly_price_usd": 39,
        "local_hardware_token_cost_usd": 0.0,
        "daily_open_weight_tokens": 2_500_000,
        "rpm_limit": 120,
        "max_concurrent_agents": 12,
        "max_active_workflows": 100,
        "fair_use_enforced": True,
        "capabilities": [
            "advanced_lifecycle_agents",
            "multi_agent_orchestration",
            "unlimited_workspace_projects",
            "kspaces_encrypted_sync",
            "priority_open_weight_routing",
            "nocode_blueprint_compiler",
        ],
    },
    "byom": {
        "id": "byom",
        "name": "Bring Your Own Model (BYOM)",
        "stream_kind": "byom_orchestration_seat",
        "monthly_price_usd": 29,
        "annual_monthly_price_usd": 24,
        "token_markup_pct": 0.0,
        "local_hardware_token_cost_usd": 0.0,
        "daily_open_weight_tokens": 500_000,
        "rpm_limit": 120,
        "max_concurrent_agents": 12,
        "max_active_workflows": 100,
        "supported_providers": sorted(SUPPORTED_BYOM_PROVIDERS),
        "platform_billing_mode": "separate_orchestration_and_workspace",
        "consumer_subscription_notice": (
            "Consumer ChatGPT Plus/Pro or Claude Pro/Max web subscriptions do NOT grant third-party "
            "API access; BYOM requires authorized developer API keys or official vendor integrations."
        ),
        "capabilities": [
            "zero_token_markup",
            "authorized_provider_api_keys",
            "self_hosted_vllm_endpoints",
            "separate_orchestration_and_workspace_billing",
            "model_license_compliance_checks",
        ],
    },
    LicenseTier.ENTERPRISE.value: {
        "id": "enterprise",
        "name": "Keelway Enterprise",
        "stream_kind": "enterprise_custom_vpc",
        "monthly_price_usd": None,
        "annual_monthly_price_usd": None,
        "pricing_label": "Custom Annual / Usage / Dedicated VPC",
        "local_hardware_token_cost_usd": 0.0,
        "daily_open_weight_tokens": 50_000_000,
        "rpm_limit": 2_000,
        "max_concurrent_agents": 128,
        "max_active_workflows": 10_000,
        "capabilities": [
            "dedicated_vpc",
            "on_prem_airgapped_deployment",
            "rbac",
            "saml_oidc_sso",
            "two_human_quorum",
            "data_retention_policies",
            "auditability",
            "custom_slas",
            "custom_agents",
        ],
    },
    "marketplace": {
        "id": "marketplace",
        "name": "Keelway Marketplace",
        "stream_kind": "ecosystem_revenue_share",
        "monthly_price_usd": 0,
        "annual_monthly_price_usd": 0,
        "revenue_splits": MARKETPLACE_SPLITS,
        "capabilities": [
            "paid_agents_and_swarms",
            "verified_skills_and_plugins",
            "automation_templates",
            "industry_enterprise_solutions",
            "pre_publish_security_validation",
        ],
    },
}


class SubscriptionPolicyEngine:
    """Evaluates 5-stream subscription quotas, BYOM credential compliance, licenses, and splits."""

    def __init__(self) -> None:
        self._daily_token_usage: Dict[str, int] = {}

    def list_tiers(self) -> List[Dict[str, Any]]:
        order = ["community", "pro", "byom", "enterprise", "marketplace"]
        return [dict(SUBSCRIPTION_TIERS[tier_id]) for tier_id in order]

    def get_tier(self, tier: str) -> Dict[str, Any]:
        tier_key = tier.strip().lower()
        if tier_key not in SUBSCRIPTION_TIERS:
            raise ValueError(f"Unsupported subscription tier '{tier}'.")
        return dict(SUBSCRIPTION_TIERS[tier_key])

    def check_quota(
        self,
        org_id: str,
        tier: str = "community",
        tokens_requested: int = 0,
        current_rpm: int = 0,
        local_hardware: bool = False,
    ) -> Dict[str, Any]:
        """Deterministic community/tier quota & fair-use checker with local-hardware fallback advice."""
        tier_spec = SUBSCRIPTION_TIERS.get(tier.strip().lower(), SUBSCRIPTION_TIERS["community"])
        tier_id = tier_spec["id"]

        if local_hardware:
            return {
                "allowed": True,
                "status": "ALLOWED",
                "org_id": org_id,
                "tier": tier_id,
                "local_hardware": True,
                "token_cost_usd": 0.0,
                "used_daily_tokens": self._daily_token_usage.get(org_id, 0),
                "remaining_daily_tokens": max(
                    0, tier_spec.get("daily_open_weight_tokens", 150_000) - self._daily_token_usage.get(org_id, 0)
                ),
                "reason": "Local hardware inference executes uncapped on user compute at $0.00/token.",
                "fallback_advice": "Active on sovereign local hardware runtime.",
            }

        daily_cap = int(tier_spec.get("daily_open_weight_tokens", 150_000))
        rpm_cap = int(tier_spec.get("rpm_limit", 20))
        used_so_far = self._daily_token_usage.get(org_id, 0)
        fallback_msg = (
            "Route to local hardware inference (Ollama / OpenCore at $0.00/tok), connect an "
            "authorized BYOM developer API key, or upgrade to Keelway Pro for higher hosted quotas."
        )

        if current_rpm > rpm_cap:
            return {
                "allowed": False,
                "status": "QUOTA_EXCEEDED",
                "org_id": org_id,
                "tier": tier_id,
                "used_daily_tokens": used_so_far,
                "remaining_daily_tokens": max(0, daily_cap - used_so_far),
                "rpm_limit": rpm_cap,
                "reason": f"RPM fair-use limit exceeded ({current_rpm} > {rpm_cap} RPM on '{tier_id}' tier).",
                "fallback_advice": fallback_msg,
            }

        if used_so_far + max(0, tokens_requested) > daily_cap:
            return {
                "allowed": False,
                "status": "QUOTA_EXCEEDED",
                "org_id": org_id,
                "tier": tier_id,
                "used_daily_tokens": used_so_far,
                "remaining_daily_tokens": max(0, daily_cap - used_so_far),
                "rpm_limit": rpm_cap,
                "reason": (
                    f"Daily community open-weight token quota exceeded "
                    f"({used_so_far + tokens_requested:,} > {daily_cap:,} tokens on '{tier_id}' tier)."
                ),
                "fallback_advice": fallback_msg,
            }

        new_used = used_so_far + max(0, tokens_requested)
        self._daily_token_usage[org_id] = new_used
        return {
            "allowed": True,
            "status": "ALLOWED",
            "org_id": org_id,
            "tier": tier_id,
            "used_daily_tokens": new_used,
            "remaining_daily_tokens": daily_cap - new_used,
            "rpm_limit": rpm_cap,
            "reason": "Within tier fair-use token and RPM quotas.",
            "fallback_advice": "Local hardware fallback remains available at $0.00/tok.",
        }

    def validate_model_license(
        self,
        model_id: str,
        license_id: str,
        commercial_use: bool = True,
        has_authorized_api_credential: bool = False,
        exceeds_700m_mau: bool = False,
    ) -> Dict[str, Any]:
        """Validates SPDX/provider license compliance against commercial-use deployment constraints."""
        norm = license_id.strip()
        if norm in {"Apache-2.0", "MIT"}:
            return {
                "allowed": True,
                "model_id": model_id,
                "license_id": norm,
                "commercial_use": commercial_use,
                "code": "LICENSE_PERMISSIVE_APPROVED",
                "obligations": ["Preserve upstream copyright and SPDX license notice in distributions."],
            }

        if norm == "Llama-3.3-Community":
            if commercial_use and exceeds_700m_mau:
                return {
                    "allowed": False,
                    "model_id": model_id,
                    "license_id": norm,
                    "commercial_use": commercial_use,
                    "code": "LICENSE_MAU_THRESHOLD_EXCEEDED",
                    "obligations": ["Requires separate custom commercial license from Meta above 700M MAU."],
                }
            return {
                "allowed": True,
                "model_id": model_id,
                "license_id": norm,
                "commercial_use": commercial_use,
                "code": "LICENSE_COMMUNITY_COMMERCIAL_APPROVED",
                "obligations": ["Include 'Built with Llama' attribution; subject to <700M MAU threshold."],
            }

        if norm == "Commercial-API":
            if commercial_use and not has_authorized_api_credential:
                return {
                    "allowed": False,
                    "model_id": model_id,
                    "license_id": norm,
                    "commercial_use": commercial_use,
                    "code": "COMMERCIAL_API_CREDENTIAL_REQUIRED",
                    "obligations": [
                        "Requires an authorized commercial API key or official enterprise agreement."
                    ],
                }
            return {
                "allowed": True,
                "model_id": model_id,
                "license_id": norm,
                "commercial_use": commercial_use,
                "code": "LICENSE_COMMERCIAL_API_APPROVED",
                "obligations": ["Governed by upstream API provider commercial terms of service."],
            }

        if commercial_use:
            return {
                "allowed": False,
                "model_id": model_id,
                "license_id": norm,
                "commercial_use": commercial_use,
                "code": "LICENSE_RESTRICTED_FOR_COMMERCIAL_USE",
                "obligations": [f"License '{norm}' is non-commercial or unverified for commercial workloads."],
            }

        return {
            "allowed": True,
            "model_id": model_id,
            "license_id": norm,
            "commercial_use": False,
            "code": "LICENSE_RESEARCH_ONLY_APPROVED",
            "obligations": ["Permitted strictly for non-commercial evaluation."],
        }

    def validate_byom_credential(
        self,
        provider: str,
        credential_kind: str,
        api_key_preview: str = "",
        model_id: str = "",
        commercial_use: bool = True,
        license_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validates BYOM provider credentials and blocks consumer web subscriptions / session cookies.
        """
        provider_norm = provider.strip().lower()
        kind_norm = credential_kind.strip().lower()
        preview = api_key_preview.strip()

        is_consumer_kind = kind_norm in {
            "consumer_subscription",
            "web_session",
            "session_cookie",
            "consumer_oauth",
            "unofficial_web_token",
        }
        matches_consumer_token = any(rx.search(preview) for rx in _CONSUMER_TOKEN_PATTERNS)

        if is_consumer_kind or matches_consumer_token:
            return {
                "valid": False,
                "code": "CREDENTIAL_TYPE_UNSUPPORTED_CONSUMER_SUBSCRIPTION",
                "provider": provider_norm,
                "credential_kind": kind_norm,
                "model_id": model_id,
                "consumer_subscription_grants_api_access": False,
                "platform_billing_mode": None,
                "message": (
                    "Consumer web subscriptions (ChatGPT Plus/Pro/Team web, Claude Pro/Max web, "
                    "browser session cookies, or unofficial web tokens) do not grant third-party API "
                    "access and are rejected unless connected via an officially supported vendor "
                    "integration. Supply an authorized API key or self-hosted endpoint credential."
                ),
            }

        if provider_norm not in SUPPORTED_BYOM_PROVIDERS:
            return {
                "valid": False,
                "code": "UNSUPPORTED_BYOM_PROVIDER",
                "provider": provider_norm,
                "credential_kind": kind_norm,
                "model_id": model_id,
                "consumer_subscription_grants_api_access": False,
                "platform_billing_mode": None,
                "message": f"Provider '{provider}' is not in supported BYOM providers {sorted(SUPPORTED_BYOM_PROVIDERS)}.",
            }

        if kind_norm not in AUTHORIZED_BYOM_KINDS or not preview:
            return {
                "valid": False,
                "code": "INVALID_BYOM_CREDENTIAL",
                "provider": provider_norm,
                "credential_kind": kind_norm,
                "model_id": model_id,
                "consumer_subscription_grants_api_access": False,
                "platform_billing_mode": None,
                "message": "BYOM requires a non-empty 'api_key' or 'official_integration' credential.",
            }

        effective_license = license_id or (
            "Apache-2.0" if provider_norm == "self_hosted_vllm" else "Commercial-API"
        )
        license_check = self.validate_model_license(
            model_id=model_id or f"{provider_norm}-default",
            license_id=effective_license,
            commercial_use=commercial_use,
            has_authorized_api_credential=True,
        )
        if not license_check["allowed"]:
            return {
                "valid": False,
                "code": license_check["code"],
                "provider": provider_norm,
                "credential_kind": kind_norm,
                "model_id": model_id,
                "consumer_subscription_grants_api_access": False,
                "platform_billing_mode": None,
                "license_check": license_check,
                "message": "; ".join(license_check["obligations"]),
            }

        return {
            "valid": True,
            "code": "BYOM_CREDENTIAL_AUTHORIZED",
            "provider": provider_norm,
            "credential_kind": kind_norm,
            "model_id": model_id,
            "consumer_subscription_grants_api_access": False,
            "platform_billing_mode": "separate_orchestration_and_workspace",
            "token_markup_pct": 0.0,
            "license_check": license_check,
            "message": (
                f"Authorized '{provider_norm}' {kind_norm} verified. Upstream model tokens bill directly "
                "to your provider account ($0 markup); Keelway bills separately for orchestration, "
                "workspace, and automation execution."
            ),
        }

    validate_byom_connection = validate_byom_credential

    def calculate_marketplace_split(self, publisher_tier: str, gross_usd: float) -> Dict[str, Any]:
        tier_key = publisher_tier.strip().lower()
        if tier_key not in MARKETPLACE_SPLITS:
            raise ValueError(f"Unknown publisher_tier '{publisher_tier}'.")
        if gross_usd < 0:
            raise ValueError("gross_usd must be non-negative.")
        split = MARKETPLACE_SPLITS[tier_key]
        creator_usd = round(gross_usd * (split["creator_share_pct"] / 100.0), 2)
        platform_usd = round(gross_usd - creator_usd, 2)
        return {
            "publisher_tier": tier_key,
            "gross_usd": round(gross_usd, 2),
            "creator_share_pct": split["creator_share_pct"],
            "platform_share_pct": split["platform_share_pct"],
            "creator_share_usd": creator_usd,
            "platform_share_usd": platform_usd,
        }


subscription_policy_engine = SubscriptionPolicyEngine()
