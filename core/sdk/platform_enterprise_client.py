"""
Keelway Client SDK — Phase 9 Enterprise Identity, SCIM 2.0, P-10 Quorum, SIEM & Observability Mixins (`client.platform`).

Defines `AsyncPlatformEnterpriseMixin` and `SyncPlatformEnterpriseMixin` inherited by
`AsyncPlatformRuntimeMixin` and `SyncPlatformRuntimeMixin` for 100% sync + async parity across
`/v1/platform/enterprise/*` and `/v1/platform/observability/metrics`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient


def _oidc_body(
    issuer_url: str,
    client_id: str,
    signing_secret: str,
    group_role_mapping: Optional[Dict[str, str]],
    enabled: bool,
    workspace_id: str,
) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "issuer_url": issuer_url,
        "client_id": client_id,
        "signing_secret": signing_secret,
        "group_role_mapping": dict(group_role_mapping or {}),
        "enabled": bool(enabled),
    }


def _scim_user_body(
    user_name: Optional[str],
    display_name: str,
    groups: Optional[List[str]],
    active: bool,
    workspace_id: str,
    user_name_camel: Optional[str],
    display_name_camel: Optional[str],
) -> Dict[str, Any]:
    resolved_user = (user_name if user_name is not None else user_name_camel) or ""
    if not str(resolved_user).strip():
        raise ValueError("user_name (or userName) must be non-empty.")
    resolved_display = display_name_camel if display_name_camel is not None else display_name
    return {
        "workspace_id": workspace_id,
        "userName": str(resolved_user).strip(),
        "displayName": resolved_display,
        "groups": list(groups or []),
        "active": bool(active),
    }


def _p10_quorum_body(
    proposal_id: str,
    approver_id: str,
    initiator_id: str,
    required_approvals: int,
    reason: str,
    workspace_id: str,
) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "proposal_id": proposal_id,
        "approver_id": approver_id,
        "initiator_id": initiator_id,
        "required_approvals": required_approvals,
        "reason": reason,
    }


class AsyncPlatformEnterpriseMixin:
    """Asynchronous Phase 9 Enterprise Identity, P-10 Quorum, SIEM & Observability methods on `AsyncKeelwayClient.platform`."""

    _client: "AsyncKeelwayClient"

    async def configure_oidc_provider(
        self,
        issuer_url: str,
        client_id: str,
        signing_secret: str = "",
        group_role_mapping: Optional[Dict[str, str]] = None,
        enabled: bool = True,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "PUT",
            "/v1/platform/enterprise/oidc",
            json=_oidc_body(issuer_url, client_id, signing_secret, group_role_mapping, enabled, workspace_id),
        )

    async def list_scim_users(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/platform/enterprise/scim/v2/Users",
            params={"workspace_id": workspace_id},
        )

    async def provision_scim_user(
        self,
        user_name: Optional[str] = None,
        display_name: str = "",
        groups: Optional[List[str]] = None,
        active: bool = True,
        workspace_id: str = "default",
        *,
        userName: Optional[str] = None,
        displayName: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/enterprise/scim/v2/Users",
            json=_scim_user_body(user_name, display_name, groups, active, workspace_id, userName, displayName),
        )

    async def approve_p10_quorum(
        self,
        proposal_id: str,
        approver_id: str,
        initiator_id: str = "",
        required_approvals: int = 2,
        reason: str = "",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/enterprise/p10-quorum/approve",
            json=_p10_quorum_body(proposal_id, approver_id, initiator_id, required_approvals, reason, workspace_id),
        )

    async def export_siem_audit(
        self,
        format: str = "ocsf",
        limit: int = 100,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/platform/enterprise/siem/export",
            params={"workspace_id": workspace_id, "format": format, "limit": limit},
        )

    async def get_observability_metrics(
        self,
        format: str = "otlp_json",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/platform/observability/metrics",
            params={"workspace_id": workspace_id, "format": format},
        )


class SyncPlatformEnterpriseMixin:
    """Synchronous Phase 9 Enterprise Identity, P-10 Quorum, SIEM & Observability methods on `KeelwayClient.platform`."""

    _client: "KeelwayClient"

    def configure_oidc_provider(
        self,
        issuer_url: str,
        client_id: str,
        signing_secret: str = "",
        group_role_mapping: Optional[Dict[str, str]] = None,
        enabled: bool = True,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "PUT",
            "/v1/platform/enterprise/oidc",
            json=_oidc_body(issuer_url, client_id, signing_secret, group_role_mapping, enabled, workspace_id),
        )

    def list_scim_users(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/platform/enterprise/scim/v2/Users",
            params={"workspace_id": workspace_id},
        )

    def provision_scim_user(
        self,
        user_name: Optional[str] = None,
        display_name: str = "",
        groups: Optional[List[str]] = None,
        active: bool = True,
        workspace_id: str = "default",
        *,
        userName: Optional[str] = None,
        displayName: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/enterprise/scim/v2/Users",
            json=_scim_user_body(user_name, display_name, groups, active, workspace_id, userName, displayName),
        )

    def approve_p10_quorum(
        self,
        proposal_id: str,
        approver_id: str,
        initiator_id: str = "",
        required_approvals: int = 2,
        reason: str = "",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/enterprise/p10-quorum/approve",
            json=_p10_quorum_body(proposal_id, approver_id, initiator_id, required_approvals, reason, workspace_id),
        )

    def export_siem_audit(
        self,
        format: str = "ocsf",
        limit: int = 100,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/platform/enterprise/siem/export",
            params={"workspace_id": workspace_id, "format": format, "limit": limit},
        )

    def get_observability_metrics(
        self,
        format: str = "otlp_json",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/platform/observability/metrics",
            params={"workspace_id": workspace_id, "format": format},
        )
