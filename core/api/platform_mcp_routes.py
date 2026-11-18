"""
FastAPI MCP Registry & Production Golden Eval Routes (`/v1/platform`).

Exposes workspace-scoped Model Context Protocol (`2025-06-18`) server registration,
built-in tool discovery & DLP-redacted tool invocation (`PlatformMcpRegistry`), and
the 16-case Golden Evaluation & Adversarial Red-Team Suite (`GoldenEvalSuite`).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import (
    _enforce_workspace_permission,
    get_rbac_controller,
)
from core.eval.golden_suite import GoldenEvalSuite, golden_eval_suite
from core.orchestration.mcp import PROTOCOL_VERSION
from core.platform.mcp_registry import PlatformMcpRegistry, platform_mcp_registry
from core.platform.rbac_webhooks import WebhookValidationError, WorkspaceRbacController
from core.security.auth import Principal, current_principal
from core.storage.workspace_fs import WorkspaceSecurityError

_PERMISSION_ALIASES: Dict[str, str] = {
    "workspaces:read": "read:all",
    "runs:start": "workflows:run",
}


def get_mcp_registry() -> PlatformMcpRegistry:
    return platform_mcp_registry


def get_golden_eval_suite() -> GoldenEvalSuite:
    return golden_eval_suite


def _slugify_server_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:64]


def _enforce_rbac(
    request: Request,
    principal: Principal,
    rbac: WorkspaceRbacController,
    workspace_id: str,
    permission: str,
) -> Dict[str, Any]:
    mapped = _PERMISSION_ALIASES.get(permission, permission)
    return _enforce_workspace_permission(request, principal, rbac, workspace_id, mapped)


router = APIRouter(
    prefix="/v1/platform",
    tags=["Unified Platform MCP & Golden Evals"],
    dependencies=[Depends(current_principal)],
)


class McpServerRegisterRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    id: Optional[str] = Field(default=None, max_length=128)
    server_id: Optional[str] = Field(default=None, max_length=128)
    name: str = Field(default="", max_length=255)
    transport: str = Field(default="sse", max_length=32)
    endpoint: str = Field(default="", max_length=2048)
    allowed_tools: Optional[List[str]] = Field(default=None)


class McpToolCallRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    tool_name: Optional[str] = Field(default=None, max_length=256)
    name: Optional[str] = Field(default=None, max_length=256)
    arguments: Optional[Dict[str, Any]] = Field(default=None)
    args: Optional[Dict[str, Any]] = Field(default=None)


class GoldenEvalRunRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    category: str = Field(default="all", max_length=64)


@router.get("/mcp/servers")
async def list_platform_mcp_servers_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    registry: PlatformMcpRegistry = Depends(get_mcp_registry),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspaces:read")
    servers = registry.list_servers(workspace_id=workspace_id)
    return {
        "workspace_id": workspace_id,
        "protocol_version": PROTOCOL_VERSION,
        "count": len(servers),
        "total": len(servers),
        "servers": servers,
    }


@router.post("/mcp/servers", status_code=status.HTTP_201_CREATED)
async def register_platform_mcp_server_route(
    req: McpServerRegisterRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    registry: PlatformMcpRegistry = Depends(get_mcp_registry),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, req.workspace_id, "webhooks:manage")
    resolved_id = (req.server_id or req.id or _slugify_server_id(req.name)).strip()
    try:
        return registry.register_server(
            workspace_id=req.workspace_id,
            server_id=resolved_id,
            name=req.name,
            transport=req.transport,
            endpoint=req.endpoint,
            allowed_tools=req.allowed_tools,
        )
    except (WebhookValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/mcp/servers/{server_id}")
async def delete_platform_mcp_server_route(
    server_id: str,
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    registry: PlatformMcpRegistry = Depends(get_mcp_registry),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "webhooks:manage")
    try:
        return registry.delete_server(workspace_id=workspace_id, server_id=server_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/mcp/tools")
async def list_platform_mcp_tools_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    registry: PlatformMcpRegistry = Depends(get_mcp_registry),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspaces:read")
    return registry.list_tools(workspace_id=workspace_id)


@router.post("/mcp/call")
async def call_platform_mcp_tool_route(
    req: McpToolCallRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    registry: PlatformMcpRegistry = Depends(get_mcp_registry),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, req.workspace_id, "runs:start")
    target_tool = (req.tool_name or req.name or "").strip()
    if not target_tool:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MCP 'tool_name' must be non-empty.")
    call_args = req.arguments if req.arguments is not None else req.args
    try:
        return registry.call_tool(
            workspace_id=req.workspace_id,
            tool_name=target_tool,
            arguments=call_args,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, WorkspaceSecurityError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/evals/golden")
async def run_platform_golden_evals_route(
    request: Request,
    req: Optional[GoldenEvalRunRequest] = Body(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    suite: GoldenEvalSuite = Depends(get_golden_eval_suite),
) -> Dict[str, Any]:
    effective = req or GoldenEvalRunRequest()
    _enforce_rbac(request, principal, rbac, effective.workspace_id, "runs:start")
    try:
        return suite.run_suite(workspace_id=effective.workspace_id, category=effective.category)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/evals/latest")
async def get_latest_platform_golden_eval_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    suite: GoldenEvalSuite = Depends(get_golden_eval_suite),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspaces:read")
    try:
        return suite.get_latest(workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
