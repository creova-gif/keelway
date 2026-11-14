"""
FastAPI Control-Plane & Workspace Routes for the Keelway Unified Agent Platform (`/v1/platform`).

Exposes the 10-View Unified Workspace overview, 5-Stream Subscription / Quota / BYOM / License
policies, Marketplace discovery & pre-publication security validation, 12 Lifecycle Agents &
P-10 Multi-Agent Team dispatch, PM issues, Product PRDs, Automation workflows, No-Code Blueprint
compilation, and the external Extension SDK.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from core.platform.enterprise import (
    EnterpriseGovernanceManager,
    EnterprisePolicyValidationError,
    enterprise_governance_manager,
)
from core.platform.marketplace import (
    MarketplaceRegistry,
    MarketplaceSecurityError,
    marketplace_registry,
)
from core.platform.signing import (
    Ed25519ManifestSigner,
    manifest_signer,
)
from core.platform.subscription import (
    SubscriptionPolicyEngine,
    subscription_policy_engine,
)
from core.platform.workspace_hub import (
    UnifiedWorkspaceHub,
    unified_workspace_hub,
)
from core.security.auth import Principal, current_principal


def get_platform_hub() -> UnifiedWorkspaceHub:
    return unified_workspace_hub


def get_marketplace_registry() -> MarketplaceRegistry:
    return marketplace_registry


def get_subscription_engine() -> SubscriptionPolicyEngine:
    return subscription_policy_engine


def get_manifest_signer() -> Ed25519ManifestSigner:
    return manifest_signer


def get_enterprise_manager() -> EnterpriseGovernanceManager:
    return enterprise_governance_manager


router = APIRouter(
    prefix="/v1/platform",
    tags=["Unified Platform"],
    dependencies=[Depends(current_principal)],
)


class QuotaCheckRequest(BaseModel):
    org_id: str = Field(default="default", min_length=1, max_length=128)
    tier: str = Field(default="community", min_length=1, max_length=64)
    tokens_requested: int = Field(default=0, ge=0)
    current_rpm: int = Field(default=0, ge=0)
    local_hardware: bool = False


class ByomValidateRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=64)
    credential_kind: str = Field(..., min_length=1, max_length=64)
    api_key_preview: str = Field(default="", max_length=256)
    model_id: str = Field(default="", max_length=128)
    commercial_use: bool = True
    license_id: Optional[str] = Field(default=None, max_length=64)


class LicenseCheckRequest(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=128)
    license_id: str = Field(..., min_length=1, max_length=64)
    commercial_use: bool = True
    has_authorized_api_credential: bool = False
    exceeds_700m_mau: bool = False


class MarketplaceInstallRequest(BaseModel):
    package_id: str = Field(..., min_length=1, max_length=128)
    workspace_id: str = Field(default="default", min_length=1, max_length=128)
    config: Optional[Dict[str, Any]] = None


class TeamDispatchRequest(BaseModel):
    team_id: str = Field(..., min_length=1, max_length=128)
    objective: str = Field(..., min_length=1, max_length=2000)
    workspace_id: str = Field(default="default", min_length=1, max_length=128)
    sensitive_mutation: bool = True


class IssueCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    workspace_id: str = Field(default="default", min_length=1, max_length=128)
    priority: str = Field(default="medium", max_length=32)
    status: str = Field(default="todo", max_length=32)
    assignee_agent: str = Field(default="feature-coder", max_length=64)
    prd_id: Optional[str] = Field(default=None, max_length=64)
    sprint_id: str = Field(default="SPR-01", max_length=64)


class PrdCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    summary: str = Field(..., min_length=1, max_length=4000)
    workspace_id: str = Field(default="default", min_length=1, max_length=128)
    acceptance_criteria: Optional[List[str]] = None


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    trigger: str = Field(default="manual", min_length=1, max_length=128)
    workspace_id: str = Field(default="default", min_length=1, max_length=128)
    nodes: Optional[List[Dict[str, Any]]] = None


class NoCodeBlueprintRequest(BaseModel):
    idea: str = Field(..., min_length=1, max_length=4000)
    workspace_id: str = Field(default="default", min_length=1, max_length=128)
    experience_mode: str = Field(default="non_coder", max_length=32)
    target_stack: str = Field(default="fastapi_react_sqlite", max_length=64)


@router.get("/overview")
async def get_platform_overview(
    workspace_id: str = Query(default="default"),
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
    mp: MarketplaceRegistry = Depends(get_marketplace_registry),
) -> Dict[str, Any]:
    installed = mp.list_installed(workspace_id=workspace_id)
    return hub.get_overview(workspace_id=workspace_id, installed_packages=installed)


@router.get("/subscriptions/tiers")
async def list_subscription_tiers(
    _: Principal = Depends(current_principal),
    engine: SubscriptionPolicyEngine = Depends(get_subscription_engine),
) -> Dict[str, Any]:
    return {"tiers": engine.list_tiers()}


@router.post("/subscriptions/quota-check")
async def check_subscription_quota(
    req: QuotaCheckRequest,
    _: Principal = Depends(current_principal),
    engine: SubscriptionPolicyEngine = Depends(get_subscription_engine),
) -> Dict[str, Any]:
    return engine.check_quota(
        org_id=req.org_id,
        tier=req.tier,
        tokens_requested=req.tokens_requested,
        current_rpm=req.current_rpm,
        local_hardware=req.local_hardware,
    )


@router.post("/subscriptions/byom/validate")
async def validate_byom_credential(
    req: ByomValidateRequest,
    _: Principal = Depends(current_principal),
    engine: SubscriptionPolicyEngine = Depends(get_subscription_engine),
) -> Dict[str, Any]:
    return engine.validate_byom_credential(
        provider=req.provider,
        credential_kind=req.credential_kind,
        api_key_preview=req.api_key_preview,
        model_id=req.model_id,
        commercial_use=req.commercial_use,
        license_id=req.license_id,
    )


@router.post("/subscriptions/license-check")
async def check_model_license(
    req: LicenseCheckRequest,
    _: Principal = Depends(current_principal),
    engine: SubscriptionPolicyEngine = Depends(get_subscription_engine),
) -> Dict[str, Any]:
    return engine.validate_model_license(
        model_id=req.model_id,
        license_id=req.license_id,
        commercial_use=req.commercial_use,
        has_authorized_api_credential=req.has_authorized_api_credential,
        exceeds_700m_mau=req.exceeds_700m_mau,
    )


@router.get("/marketplace/packages")
async def list_marketplace_packages(
    kind: Optional[str] = Query(default=None),
    query: Optional[str] = Query(default=None),
    publisher_tier: Optional[str] = Query(default=None),
    workspace_id: str = Query(default="default"),
    _: Principal = Depends(current_principal),
    mp: MarketplaceRegistry = Depends(get_marketplace_registry),
) -> Dict[str, Any]:
    packages = mp.list_packages(kind=kind, query=query, publisher_tier=publisher_tier)
    return {
        "packages": packages,
        "total": len(packages),
        "installed": mp.list_installed(workspace_id=workspace_id),
    }


@router.post("/marketplace/scan")
async def scan_marketplace_package(
    payload: Dict[str, Any] = Body(...),
    _: Principal = Depends(current_principal),
    mp: MarketplaceRegistry = Depends(get_marketplace_registry),
) -> Dict[str, Any]:
    return mp.scanner.scan_package(payload)


@router.post("/marketplace/publish", status_code=status.HTTP_201_CREATED)
async def publish_marketplace_package(
    payload: Dict[str, Any] = Body(...),
    _: Principal = Depends(current_principal),
    mp: MarketplaceRegistry = Depends(get_marketplace_registry),
) -> Dict[str, Any]:
    try:
        return mp.publish_package(payload)
    except MarketplaceSecurityError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.report,
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"passed": False, "message": str(exc)},
        ) from exc


@router.post("/marketplace/install")
async def install_marketplace_package(
    req: MarketplaceInstallRequest,
    _: Principal = Depends(current_principal),
    mp: MarketplaceRegistry = Depends(get_marketplace_registry),
) -> Dict[str, Any]:
    try:
        return mp.install_package(
            package_id=req.package_id,
            workspace_id=req.workspace_id,
            config=req.config,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/marketplace/uninstall")
async def uninstall_marketplace_package(
    req: MarketplaceInstallRequest,
    _: Principal = Depends(current_principal),
    mp: MarketplaceRegistry = Depends(get_marketplace_registry),
) -> Dict[str, Any]:
    return mp.uninstall_package(package_id=req.package_id, workspace_id=req.workspace_id)


@router.get("/agents")
async def get_lifecycle_agents(
    workspace_id: str = Query(default="default"),
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    catalog = hub.list_agents_and_teams()
    catalog["runs"] = hub.list_team_runs(workspace_id=workspace_id)
    return catalog


@router.post("/agents/teams/dispatch")
async def dispatch_multi_agent_team(
    req: TeamDispatchRequest,
    principal: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    try:
        return hub.dispatch_agent_team(
            team_id=req.team_id,
            objective=req.objective,
            workspace_id=req.workspace_id,
            sensitive_mutation=req.sensitive_mutation,
            requested_by=principal.actor,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/pm/issues")
async def list_pm_issues(
    workspace_id: str = Query(default="default"),
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    issues = hub.list_issues(workspace_id=workspace_id)
    return {"issues": issues, "total": len(issues)}


@router.post("/pm/issues", status_code=status.HTTP_201_CREATED)
async def create_pm_issue(
    req: IssueCreateRequest,
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    return hub.create_issue(
        title=req.title,
        workspace_id=req.workspace_id,
        priority=req.priority,
        status=req.status,
        assignee_agent=req.assignee_agent,
        prd_id=req.prd_id,
        sprint_id=req.sprint_id,
    )


@router.get("/product/prds")
async def list_product_prds(
    workspace_id: str = Query(default="default"),
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    prds = hub.list_prds(workspace_id=workspace_id)
    return {"prds": prds, "total": len(prds)}


@router.post("/product/prds", status_code=status.HTTP_201_CREATED)
async def create_product_prd(
    req: PrdCreateRequest,
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    return hub.create_prd(
        title=req.title,
        summary=req.summary,
        workspace_id=req.workspace_id,
        acceptance_criteria=req.acceptance_criteria,
    )


@router.get("/automation/workflows")
async def list_automation_workflows(
    workspace_id: str = Query(default="default"),
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    workflows = hub.list_workflows(workspace_id=workspace_id)
    return {"workflows": workflows, "total": len(workflows)}


@router.post("/automation/workflows", status_code=status.HTTP_201_CREATED)
async def create_automation_workflow(
    req: WorkflowCreateRequest,
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    return hub.create_workflow(
        name=req.name,
        trigger=req.trigger,
        nodes=req.nodes,
        workspace_id=req.workspace_id,
    )


@router.post("/nocode/blueprint")
async def compile_nocode_blueprint(
    req: NoCodeBlueprintRequest,
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    try:
        return hub.compile_nocode_blueprint(
            idea=req.idea,
            workspace_id=req.workspace_id,
            experience_mode=req.experience_mode,
            target_stack=req.target_stack,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/extensions")
async def list_registered_extensions(
    extension_type: Optional[str] = Query(default=None),
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    exts = hub.extensions.list_extensions(extension_type=extension_type)
    return {"extensions": exts, "total": len(exts)}


@router.post("/extensions/register", status_code=status.HTTP_201_CREATED)
async def register_platform_extension(
    spec: Dict[str, Any] = Body(...),
    _: Principal = Depends(current_principal),
    hub: UnifiedWorkspaceHub = Depends(get_platform_hub),
) -> Dict[str, Any]:
    try:
        return hub.extensions.register_extension(spec)
    except MarketplaceSecurityError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.report,
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"passed": False, "message": str(exc)},
        ) from exc


class ComplianceCheckRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    framework: str = Field(..., min_length=1, max_length=32)


@router.post("/marketplace/verify-signature")
async def verify_marketplace_manifest_signature(
    payload: Dict[str, Any] = Body(...),
    _: Principal = Depends(current_principal),
    signer: Ed25519ManifestSigner = Depends(get_manifest_signer),
) -> Dict[str, Any]:
    manifest = payload["manifest"] if isinstance(payload.get("manifest"), dict) else payload
    extra_keys = payload.get("trusted_keys") if isinstance(payload.get("trusted_keys"), dict) else None
    active_signer = signer
    if extra_keys:
        merged = signer.list_trusted_keys()
        merged.update({str(k): str(v) for k, v in extra_keys.items()})
        try:
            active_signer = Ed25519ManifestSigner(trusted_keys=merged)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    valid, reason = active_signer.verify_manifest(manifest)
    return {
        "valid": valid,
        "status": reason,
        "reason": reason,
        "signer_key_id": manifest.get("signer_key_id"),
        "schema": manifest.get("schema"),
    }


@router.get("/enterprise/policy/{tenant_id}")
async def get_enterprise_tenant_policy(
    tenant_id: str,
    _: Principal = Depends(current_principal),
    mgr: EnterpriseGovernanceManager = Depends(get_enterprise_manager),
) -> Dict[str, Any]:
    try:
        return mgr.get_policy(tenant_id)
    except EnterprisePolicyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/enterprise/policy/{tenant_id}")
async def put_enterprise_tenant_policy(
    tenant_id: str,
    payload: Dict[str, Any] = Body(...),
    _: Principal = Depends(current_principal),
    mgr: EnterpriseGovernanceManager = Depends(get_enterprise_manager),
) -> Dict[str, Any]:
    try:
        return mgr.upsert_policy(tenant_id, payload)
    except (EnterprisePolicyValidationError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/enterprise/compliance-check")
async def evaluate_enterprise_compliance(
    req: ComplianceCheckRequest,
    _: Principal = Depends(current_principal),
    mgr: EnterpriseGovernanceManager = Depends(get_enterprise_manager),
) -> Dict[str, Any]:
    try:
        return mgr.evaluate_compliance_posture(tenant_id=req.tenant_id, framework=req.framework)
    except EnterprisePolicyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
