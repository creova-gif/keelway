"""
Enterprise Governance, Data Retention, Deployment Topologies & Compliance Evaluator (Pillar 6 & 7).

Provides tenant-isolated governance policies (`tenant_id`) covering data retention modes,
DLP/PII redaction, custom organization branding, VPC / air-gapped deployment profiles,
resource caps, and deterministic compliance evaluation against SOC2, HIPAA, ISO27001, and GDPR.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.platform.persistence import SQLitePlatformStore

VALID_RETENTION_MODES: Dict[str, int] = {
    "ephemeral_0d": 0,
    "standard_30d": 30,
    "regulated_365d": 365,
    "worm_7y": 2555,
}
VALID_DEPLOYMENT_TOPOLOGIES = frozenset(
    {
        "local_workstation",
        "dedicated_vpc",
        "on_prem_airgapped",
    }
)
SUPPORTED_COMPLIANCE_FRAMEWORKS = frozenset({"SOC2", "HIPAA", "ISO27001", "GDPR"})


class EnterprisePolicyValidationError(ValueError):
    """Raised when an enterprise governance policy fails strict schema or domain validation."""


def _default_tenant_policy(tenant_id: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "tenant_id": tenant_id,
        "org_display_name": f"{tenant_id} Organization",
        "retention_mode": "standard_30d",
        "audit_retention_days": 30,
        "pii_redaction_enforced": True,
        "allow_prompt_logging": False,
        "deployment_topology": "local_workstation",
        "allowed_model_regions": ["local"],
        "sso_saml_required": False,
        "branding": {
            "logo_url": "",
            "accent_hex": "#2DD4BF",
            "badge_label": "Keelway Sovereign",
        },
        "max_concurrent_sandboxes": 8,
        "max_workflow_minutes_per_day": 480,
        "require_p10_for_external_webhooks": True,
        "resource_caps": {
            "max_concurrent_sandboxes": 8,
            "max_workflow_minutes_per_day": 480,
            "require_p10_for_external_webhooks": True,
        },
        "updated_at": now,
    }


class EnterpriseGovernanceManager:
    """Tenant-isolated Enterprise Governance & Compliance Posture manager."""

    def __init__(self, store: Optional[SQLitePlatformStore] = None) -> None:
        self.store = store
        self._policies: Dict[str, Dict[str, Any]] = {}
        if self.store is not None:
            for saved in self.store.list_records_by_collection("enterprise_policies"):
                tid = str(saved.get("tenant_id") or "").strip()
                if tid:
                    self._policies[tid] = dict(saved)

    @staticmethod
    def _clean_tenant_id(tenant_id: str) -> str:
        clean = str(tenant_id or "").strip()
        if not clean:
            raise EnterprisePolicyValidationError("Enterprise 'tenant_id' must be non-empty.")
        return clean

    def get_policy(self, tenant_id: str) -> Dict[str, Any]:
        tid = self._clean_tenant_id(tenant_id)
        if tid in self._policies:
            return dict(self._policies[tid])
        if self.store is not None:
            persisted = self.store.get_record(tid, "enterprise_policies", tid)
            if persisted is not None:
                self._policies[tid] = dict(persisted)
                return dict(persisted)
        return _default_tenant_policy(tid)

    def upsert_policy(self, tenant_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        tid = self._clean_tenant_id(tenant_id)
        current = self.get_policy(tid)

        retention_mode = str(payload.get("retention_mode", current["retention_mode"])).strip()
        if retention_mode not in VALID_RETENTION_MODES:
            raise EnterprisePolicyValidationError(
                f"Invalid retention_mode '{retention_mode}'. "
                f"Expected one of {sorted(VALID_RETENTION_MODES.keys())}."
            )

        topology = str(payload.get("deployment_topology", current["deployment_topology"])).strip()
        if topology not in VALID_DEPLOYMENT_TOPOLOGIES:
            raise EnterprisePolicyValidationError(
                f"Invalid deployment_topology '{topology}'. "
                f"Expected one of {sorted(VALID_DEPLOYMENT_TOPOLOGIES)}."
            )

        default_days = VALID_RETENTION_MODES[retention_mode]
        raw_days = payload.get("audit_retention_days")
        audit_retention_days = default_days if raw_days is None else int(raw_days)
        if audit_retention_days < 0:
            raise EnterprisePolicyValidationError("audit_retention_days must be >= 0.")

        incoming_caps = payload.get("resource_caps") if isinstance(payload.get("resource_caps"), dict) else {}
        max_sandboxes = int(
            payload.get(
                "max_concurrent_sandboxes",
                incoming_caps.get("max_concurrent_sandboxes", current["max_concurrent_sandboxes"]),
            )
        )
        max_wf_minutes = int(
            payload.get(
                "max_workflow_minutes_per_day",
                incoming_caps.get("max_workflow_minutes_per_day", current["max_workflow_minutes_per_day"]),
            )
        )
        if max_sandboxes < 1 or max_wf_minutes < 1:
            raise EnterprisePolicyValidationError(
                "Resource caps max_concurrent_sandboxes and max_workflow_minutes_per_day must be >= 1."
            )

        require_p10_webhooks = bool(
            payload.get(
                "require_p10_for_external_webhooks",
                incoming_caps.get(
                    "require_p10_for_external_webhooks",
                    current["require_p10_for_external_webhooks"],
                ),
            )
        )

        incoming_branding = payload.get("branding") if isinstance(payload.get("branding"), dict) else {}
        merged_branding = {
            "logo_url": str(incoming_branding.get("logo_url", payload.get("logo_url", current["branding"]["logo_url"]))),
            "accent_hex": str(
                incoming_branding.get("accent_hex", payload.get("accent_hex", current["branding"]["accent_hex"]))
            ),
            "badge_label": str(
                incoming_branding.get("badge_label", payload.get("badge_label", current["branding"]["badge_label"]))
            ),
        }

        raw_regions = payload.get("allowed_model_regions", current["allowed_model_regions"])
        if not isinstance(raw_regions, list) or not raw_regions:
            raise EnterprisePolicyValidationError("allowed_model_regions must be a non-empty list of regions.")
        allowed_regions = [str(r).strip() for r in raw_regions if str(r).strip()]
        if not allowed_regions:
            raise EnterprisePolicyValidationError("allowed_model_regions must contain at least one valid region.")

        now = datetime.now(timezone.utc).isoformat()
        record: Dict[str, Any] = {
            "tenant_id": tid,
            "org_display_name": str(payload.get("org_display_name") or current["org_display_name"]).strip(),
            "retention_mode": retention_mode,
            "audit_retention_days": audit_retention_days,
            "pii_redaction_enforced": bool(
                payload.get("pii_redaction_enforced", current["pii_redaction_enforced"])
            ),
            "allow_prompt_logging": bool(payload.get("allow_prompt_logging", current["allow_prompt_logging"])),
            "deployment_topology": topology,
            "allowed_model_regions": allowed_regions,
            "sso_saml_required": bool(payload.get("sso_saml_required", current["sso_saml_required"])),
            "branding": merged_branding,
            "max_concurrent_sandboxes": max_sandboxes,
            "max_workflow_minutes_per_day": max_wf_minutes,
            "require_p10_for_external_webhooks": require_p10_webhooks,
            "resource_caps": {
                "max_concurrent_sandboxes": max_sandboxes,
                "max_workflow_minutes_per_day": max_wf_minutes,
                "require_p10_for_external_webhooks": require_p10_webhooks,
            },
            "updated_at": now,
        }
        self._policies[tid] = record
        if self.store is not None:
            self.store.upsert_record(tid, "enterprise_policies", tid, record, updated_at=now)
        return dict(record)

    def evaluate_compliance_posture(self, tenant_id: str, framework: str) -> Dict[str, Any]:
        tid = self._clean_tenant_id(tenant_id)
        fw = str(framework or "").strip().upper()
        if fw not in SUPPORTED_COMPLIANCE_FRAMEWORKS:
            raise EnterprisePolicyValidationError(
                f"Unsupported compliance framework '{framework}'. "
                f"Expected one of {sorted(SUPPORTED_COMPLIANCE_FRAMEWORKS)}."
            )

        pol = self.get_policy(tid)
        controls: List[Dict[str, Any]] = []
        remediations: List[str] = []

        def _check(control_id: str, title: str, condition: bool, remediation: str) -> None:
            controls.append(
                {
                    "control_id": control_id,
                    "title": title,
                    "passed": bool(condition),
                    "remediation": None if condition else remediation,
                }
            )
            if not condition:
                remediations.append(remediation)

        if fw == "SOC2":
            _check(
                "SOC2-CC6.1",
                "SAML / OIDC Single Sign-On Required",
                pol["sso_saml_required"] is True,
                "Enable SAML/OIDC Single Sign-On (`sso_saml_required=True`).",
            )
            _check(
                "SOC2-CC6.6",
                "DLP & PII Redaction Enforced",
                pol["pii_redaction_enforced"] is True,
                "Enforce deterministic PII/secret redaction (`pii_redaction_enforced=True`).",
            )
            _check(
                "SOC2-CC7.2",
                "365-Day Audit Retention Minimum",
                pol["retention_mode"] in {"regulated_365d", "worm_7y"} and pol["audit_retention_days"] >= 365,
                "Configure `regulated_365d` or `worm_7y` retention with `audit_retention_days >= 365`.",
            )
            _check(
                "SOC2-CC8.1",
                "Human P-10 External Webhook Gate",
                pol["require_p10_for_external_webhooks"] is True,
                "Require human P-10 approval for external webhooks (`require_p10_for_external_webhooks=True`).",
            )
        elif fw == "HIPAA":
            _check(
                "HIPAA-164.312(a)",
                "Federated SSO Access Control",
                pol["sso_saml_required"] is True,
                "Enable federated SAML/SSO access control (`sso_saml_required=True`).",
            )
            _check(
                "HIPAA-164.312(b)",
                "WORM 6-7 Year Audit Record Retention",
                pol["retention_mode"] == "worm_7y" and pol["audit_retention_days"] >= 2190,
                "Set `retention_mode='worm_7y'` (`audit_retention_days >= 2190`) for HIPAA audit logs.",
            )
            _check(
                "HIPAA-164.312(e)",
                "PHI Redaction & Zero Raw Prompt Logging",
                pol["pii_redaction_enforced"] is True and pol["allow_prompt_logging"] is False,
                "Enforce PHI redaction (`pii_redaction_enforced=True`) and disable `allow_prompt_logging`.",
            )
            _check(
                "HIPAA-164.308(a)",
                "Isolated VPC / Air-Gapped Topology & P-10 Egress Gate",
                pol["deployment_topology"] in {"dedicated_vpc", "on_prem_airgapped"}
                and pol["require_p10_for_external_webhooks"] is True,
                "Deploy in `dedicated_vpc` or `on_prem_airgapped` topology with P-10 webhook gating.",
            )
        elif fw == "ISO27001":
            _check(
                "ISO-A.8.2",
                "Privileged Access & SSO Federation",
                pol["sso_saml_required"] is True,
                "Require SSO/SAML authentication (`sso_saml_required=True`).",
            )
            _check(
                "ISO-A.8.12",
                "Data Leakage Prevention & P-10 Egress Control",
                pol["pii_redaction_enforced"] is True and pol["require_p10_for_external_webhooks"] is True,
                "Enforce `pii_redaction_enforced=True` and `require_p10_for_external_webhooks=True`.",
            )
            _check(
                "ISO-A.8.15",
                "Regulated Audit Trail Retention",
                pol["retention_mode"] in {"regulated_365d", "worm_7y"} and pol["audit_retention_days"] >= 365,
                "Retain audit trails for >= 365 days (`regulated_365d` or `worm_7y`).",
            )
            _check(
                "ISO-A.8.20",
                "Network Segregation (`dedicated_vpc` or `on_prem_airgapped`)",
                pol["deployment_topology"] in {"dedicated_vpc", "on_prem_airgapped"},
                "Isolate tenant runtime in `dedicated_vpc` or `on_prem_airgapped` topology.",
            )
        else:  # GDPR
            _check(
                "GDPR-ART5.1(c)",
                "Data Minimization & PII Redaction",
                pol["pii_redaction_enforced"] is True and pol["allow_prompt_logging"] is False,
                "Set `pii_redaction_enforced=True` and `allow_prompt_logging=False` for data minimization.",
            )
            _check(
                "GDPR-ART5.1(e)",
                "Storage Limitation Policy",
                pol["retention_mode"] in {"ephemeral_0d", "standard_30d", "regulated_365d"},
                "Use bounded retention (`ephemeral_0d`, `standard_30d`, or `regulated_365d`) under GDPR Art. 5(1)(e).",
            )
            _check(
                "GDPR-ART32",
                "Security of Processing & P-10 Egress Gate",
                pol["require_p10_for_external_webhooks"] is True,
                "Require human P-10 approval before external webhook data transfers.",
            )
            _check(
                "GDPR-ART44",
                "Sovereign Local or EU Model Region Residency",
                all(r == "local" or r.startswith("eu-") for r in pol["allowed_model_regions"]),
                "Restrict `allowed_model_regions` to `local` or `eu-*` sovereign jurisdictions.",
            )

        passed_count = sum(1 for c in controls if c["passed"])
        return {
            "tenant_id": tid,
            "framework": fw,
            "passed": passed_count == len(controls),
            "score_pct": round(100.0 * passed_count / len(controls), 1),
            "controls": controls,
            "remediations": remediations,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }


enterprise_governance_manager = EnterpriseGovernanceManager()
