"""
Keelway Client SDK — Unified Platform Namespace (`client.platform`).

Provides 100% synchronous (`SyncPlatformClient`) and asynchronous (`AsyncPlatformClient`)
parity across `/v1/platform/*`: 10-View Workspace overview, 5-Stream Subscriptions / Quotas /
BYOM / SPDX Model Licenses, Marketplace discovery & security-gated publishing, 12 Lifecycle
Agents & P-10 Team dispatch, PM Issues, Product PRDs, Automation Workflows, No-Code Blueprints,
and External SDK Extensions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.sdk.platform_runtime_client import (
    AsyncPlatformRuntimeMixin,
    SyncPlatformRuntimeMixin,
)

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient


def _quota_body(org_id: str, tier: str, tokens_requested: int, current_rpm: int, local_hardware: bool) -> Dict[str, Any]:
    return {
        "org_id": org_id,
        "tier": tier,
        "tokens_requested": tokens_requested,
        "current_rpm": current_rpm,
        "local_hardware": local_hardware,
    }


def _byom_body(
    provider: str,
    credential_kind: str,
    api_key_preview: str,
    model_id: Optional[str],
    commercial_use: bool,
    license_id: Optional[str],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "provider": provider,
        "credential_kind": credential_kind,
        "api_key_preview": api_key_preview,
        "model_id": model_id if model_id is not None else "",
        "commercial_use": commercial_use,
    }
    if license_id is not None:
        body["license_id"] = license_id
    return body


def _license_body(
    model_id: str,
    license_id: str,
    commercial_use: bool,
    has_authorized_api_key: bool,
    has_authorized_api_credential: Optional[bool],
    exceeds_700m_mau: bool,
) -> Dict[str, Any]:
    return {
        "model_id": model_id,
        "license_id": license_id,
        "commercial_use": commercial_use,
        "has_authorized_api_credential": (
            has_authorized_api_credential if has_authorized_api_credential is not None else has_authorized_api_key
        ),
        "exceeds_700m_mau": exceeds_700m_mau,
    }


def _marketplace_query(kind: Optional[str], query: Optional[str], publisher_tier: Optional[str], workspace_id: str) -> Dict[str, Any]:
    params: Dict[str, Any] = {"workspace_id": workspace_id}
    if kind is not None:
        params["kind"] = kind
    if query is not None:
        params["query"] = query
    if publisher_tier is not None:
        params["publisher_tier"] = publisher_tier
    return params


def _issue_body(
    title: str,
    workspace_id: str,
    priority: str,
    status: str,
    assignee_agent: str,
    prd_id: Optional[str],
    sprint_id: str,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "title": title,
        "workspace_id": workspace_id,
        "priority": priority,
        "status": status,
        "assignee_agent": assignee_agent,
        "sprint_id": sprint_id,
    }
    if prd_id is not None:
        body["prd_id"] = prd_id
    return body


def _filter_issues_by_status(res: Dict[str, Any], status: Optional[str]) -> Dict[str, Any]:
    if status is None or not isinstance(res, dict) or not isinstance(res.get("issues"), list):
        return res
    filtered = [item for item in res["issues"] if item.get("status") == status]
    return {**res, "issues": filtered, "total": len(filtered)}


class AsyncPlatformClient(AsyncPlatformRuntimeMixin):
    """Asynchronous `/v1/platform/*` sub-client attached at `AsyncKeelwayClient.platform`."""

    def __init__(self, client: "AsyncKeelwayClient") -> None:
        self._client = client

    async def overview(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/overview", params={"workspace_id": workspace_id})

    async def list_tiers(self) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/subscriptions/tiers")

    async def check_quota(
        self, org_id: str, tier: str, tokens_requested: int, current_rpm: int = 1, local_hardware: bool = False
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST", "/v1/platform/subscriptions/quota-check", json=_quota_body(org_id, tier, tokens_requested, current_rpm, local_hardware)
        )

    async def validate_byom(
        self,
        provider: str,
        credential_kind: str,
        api_key_preview: str = "",
        model_id: Optional[str] = None,
        commercial_use: bool = True,
        license_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/subscriptions/byom/validate",
            json=_byom_body(provider, credential_kind, api_key_preview, model_id, commercial_use, license_id),
        )

    async def check_model_license(
        self,
        model_id: str,
        license_id: str,
        commercial_use: bool = True,
        has_authorized_api_key: bool = False,
        *,
        has_authorized_api_credential: Optional[bool] = None,
        exceeds_700m_mau: bool = False,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/subscriptions/license-check",
            json=_license_body(model_id, license_id, commercial_use, has_authorized_api_key, has_authorized_api_credential, exceeds_700m_mau),
        )

    async def list_marketplace_packages(
        self, kind: Optional[str] = None, query: Optional[str] = None, publisher_tier: Optional[str] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET", "/v1/platform/marketplace/packages", params=_marketplace_query(kind, query, publisher_tier, workspace_id)
        )

    async def scan_marketplace_package(self, package: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/marketplace/scan", json=package)

    async def publish_marketplace_package(self, package: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/marketplace/publish", json=package)

    async def install_marketplace_package(
        self, package_id: str, workspace_id: str = "default", config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"package_id": package_id, "workspace_id": workspace_id}
        if config is not None:
            body["config"] = config
        return await self._client._req("POST", "/v1/platform/marketplace/install", json=body)

    async def purchase_marketplace_package(
        self,
        package_id: str,
        buyer_tenant_id: str = "default",
        workspace_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"package_id": package_id, "buyer_tenant_id": buyer_tenant_id}
        if workspace_id is not None:
            body["workspace_id"] = workspace_id
        if config is not None:
            body["config"] = config
        return await self._client._req("POST", "/v1/platform/marketplace/purchase", json=body)

    async def list_marketplace_settlements(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        params: Optional[Dict[str, Any]] = {"tenant_id": tenant_id} if tenant_id is not None else None
        return await self._client._req("GET", "/v1/platform/marketplace/settlements", params=params)

    async def list_agents(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/agents", params={"workspace_id": workspace_id})

    async def dispatch_team(
        self,
        team_id: str,
        goal: str = "",
        workspace_id: str = "default",
        sensitive_mutation: bool = False,
        *,
        objective: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/agents/teams/dispatch",
            json={
                "team_id": team_id,
                "objective": objective if objective is not None else goal,
                "workspace_id": workspace_id,
                "sensitive_mutation": sensitive_mutation,
            },
        )

    async def list_issues(self, workspace_id: str = "default", status: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"workspace_id": workspace_id, **({"status": status} if status is not None else {})}
        return _filter_issues_by_status(await self._client._req("GET", "/v1/platform/pm/issues", params=params), status)

    async def create_issue(
        self,
        title: str,
        workspace_id: str = "default",
        priority: str = "medium",
        status: str = "todo",
        assignee_agent: str = "feature-coder",
        prd_id: Optional[str] = None,
        sprint_id: str = "SPR-01",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST", "/v1/platform/pm/issues", json=_issue_body(title, workspace_id, priority, status, assignee_agent, prd_id, sprint_id)
        )

    async def list_prds(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/product/prds", params={"workspace_id": workspace_id})

    async def create_prd(
        self, title: str, summary: str, workspace_id: str = "default", acceptance_criteria: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"title": title, "summary": summary, "workspace_id": workspace_id}
        if acceptance_criteria is not None:
            body["acceptance_criteria"] = acceptance_criteria
        return await self._client._req("POST", "/v1/platform/product/prds", json=body)

    async def list_workflows(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/automation/workflows", params={"workspace_id": workspace_id})

    async def create_workflow(
        self, name: str, trigger: str = "manual", workspace_id: str = "default", nodes: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"name": name, "trigger": trigger, "workspace_id": workspace_id}
        if nodes is not None:
            body["nodes"] = nodes
        return await self._client._req("POST", "/v1/platform/automation/workflows", json=body)

    async def compile_blueprint(
        self,
        idea: str,
        workspace_id: str = "default",
        experience_mode: str = "non_coder",
        target_stack: str = "react-fastapi-sqlite",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/nocode/blueprint",
            json={"idea": idea, "workspace_id": workspace_id, "experience_mode": experience_mode, "target_stack": target_stack},
        )

    async def list_extensions(self, workspace_id: str = "default", extension_type: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"workspace_id": workspace_id, **({"extension_type": extension_type} if extension_type is not None else {})}
        return await self._client._req("GET", "/v1/platform/extensions", params=params)

    async def register_extension(self, extension: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/extensions/register", json=extension)


class SyncPlatformClient(SyncPlatformRuntimeMixin):
    """Synchronous `/v1/platform/*` sub-client attached at `KeelwayClient.platform`."""

    def __init__(self, client: "KeelwayClient") -> None:
        self._client = client

    def overview(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/overview", params={"workspace_id": workspace_id})

    def list_tiers(self) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/subscriptions/tiers")

    def check_quota(
        self, org_id: str, tier: str, tokens_requested: int, current_rpm: int = 1, local_hardware: bool = False
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST", "/v1/platform/subscriptions/quota-check", json=_quota_body(org_id, tier, tokens_requested, current_rpm, local_hardware)
        )

    def validate_byom(
        self,
        provider: str,
        credential_kind: str,
        api_key_preview: str = "",
        model_id: Optional[str] = None,
        commercial_use: bool = True,
        license_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/subscriptions/byom/validate",
            json=_byom_body(provider, credential_kind, api_key_preview, model_id, commercial_use, license_id),
        )

    def check_model_license(
        self,
        model_id: str,
        license_id: str,
        commercial_use: bool = True,
        has_authorized_api_key: bool = False,
        *,
        has_authorized_api_credential: Optional[bool] = None,
        exceeds_700m_mau: bool = False,
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/subscriptions/license-check",
            json=_license_body(model_id, license_id, commercial_use, has_authorized_api_key, has_authorized_api_credential, exceeds_700m_mau),
        )

    def list_marketplace_packages(
        self, kind: Optional[str] = None, query: Optional[str] = None, publisher_tier: Optional[str] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET", "/v1/platform/marketplace/packages", params=_marketplace_query(kind, query, publisher_tier, workspace_id)
        )

    def scan_marketplace_package(self, package: Dict[str, Any]) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/marketplace/scan", json=package)

    def publish_marketplace_package(self, package: Dict[str, Any]) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/marketplace/publish", json=package)

    def install_marketplace_package(
        self, package_id: str, workspace_id: str = "default", config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"package_id": package_id, "workspace_id": workspace_id}
        if config is not None:
            body["config"] = config
        return self._client._req("POST", "/v1/platform/marketplace/install", json=body)

    def purchase_marketplace_package(
        self,
        package_id: str,
        buyer_tenant_id: str = "default",
        workspace_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"package_id": package_id, "buyer_tenant_id": buyer_tenant_id}
        if workspace_id is not None:
            body["workspace_id"] = workspace_id
        if config is not None:
            body["config"] = config
        return self._client._req("POST", "/v1/platform/marketplace/purchase", json=body)

    def list_marketplace_settlements(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        params: Optional[Dict[str, Any]] = {"tenant_id": tenant_id} if tenant_id is not None else None
        return self._client._req("GET", "/v1/platform/marketplace/settlements", params=params)

    def list_agents(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/agents", params={"workspace_id": workspace_id})

    def dispatch_team(
        self,
        team_id: str,
        goal: str = "",
        workspace_id: str = "default",
        sensitive_mutation: bool = False,
        *,
        objective: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/agents/teams/dispatch",
            json={
                "team_id": team_id,
                "objective": objective if objective is not None else goal,
                "workspace_id": workspace_id,
                "sensitive_mutation": sensitive_mutation,
            },
        )

    def list_issues(self, workspace_id: str = "default", status: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"workspace_id": workspace_id, **({"status": status} if status is not None else {})}
        return _filter_issues_by_status(self._client._req("GET", "/v1/platform/pm/issues", params=params), status)

    def create_issue(
        self,
        title: str,
        workspace_id: str = "default",
        priority: str = "medium",
        status: str = "todo",
        assignee_agent: str = "feature-coder",
        prd_id: Optional[str] = None,
        sprint_id: str = "SPR-01",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST", "/v1/platform/pm/issues", json=_issue_body(title, workspace_id, priority, status, assignee_agent, prd_id, sprint_id)
        )

    def list_prds(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/product/prds", params={"workspace_id": workspace_id})

    def create_prd(
        self, title: str, summary: str, workspace_id: str = "default", acceptance_criteria: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"title": title, "summary": summary, "workspace_id": workspace_id}
        if acceptance_criteria is not None:
            body["acceptance_criteria"] = acceptance_criteria
        return self._client._req("POST", "/v1/platform/product/prds", json=body)

    def list_workflows(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/automation/workflows", params={"workspace_id": workspace_id})

    def create_workflow(
        self, name: str, trigger: str = "manual", workspace_id: str = "default", nodes: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"name": name, "trigger": trigger, "workspace_id": workspace_id}
        if nodes is not None:
            body["nodes"] = nodes
        return self._client._req("POST", "/v1/platform/automation/workflows", json=body)

    def compile_blueprint(
        self,
        idea: str,
        workspace_id: str = "default",
        experience_mode: str = "non_coder",
        target_stack: str = "react-fastapi-sqlite",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/nocode/blueprint",
            json={"idea": idea, "workspace_id": workspace_id, "experience_mode": experience_mode, "target_stack": target_stack},
        )

    def list_extensions(self, workspace_id: str = "default", extension_type: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"workspace_id": workspace_id, **({"extension_type": extension_type} if extension_type is not None else {})}
        return self._client._req("GET", "/v1/platform/extensions", params=params)

    def register_extension(self, extension: Dict[str, Any]) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/extensions/register", json=extension)
