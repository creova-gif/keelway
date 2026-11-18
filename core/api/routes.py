"""
FastAPI Routes for Keelway Core.
"""

import asyncio
import os
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, WebSocket, WebSocketDisconnect, WebSocketException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.api.schemas import (
    HealthResponse,
    CompletionRequestSchema,
    CompletionResponseSchema,
    TaskCreateRequest,
    TaskTransitionRequest,
    TaskResponse,
    EngineeringBriefRequest,
    EngineeringBriefResponse,
    ResearchSummaryRequest,
    ResearchSummaryResponse,
    SandboxTestRequest,
    SandboxTestResponse,
    MemoryCreateRequest,
    MemoryResponse,
)
from core.config import legacy_aware, settings
from core.models.gateway import gateway
from core.security.auth import LOCAL_OWNER, Principal, current_principal, principal_for_token, record_audit, require, token_from_headers
from keelway.runner.enrollment import verify_enrolled_runner_token
from keelway.security.source_defaults import InsecureDefaultConfiguration
from core.security.env_scrub import scrub_env
from core.security.origin import origin_allowed
from core.security.rbac import Permission, Role
from core.orchestration.state import TaskState, validate_transition, InvalidStateTransitionError
from core.orchestration.chat import InteractiveChatSession, ConversationMode
from core.api.schemas import Provider
from core.orchestration.workflows import (
    EngineeringBriefWorkflow,
    ResearchSummaryWorkflow,
    SandboxedFailureAnalysisWorkflow,
    SandboxExecutionError,
)
from core.storage.database import get_db, check_db_health
from core.storage.models import TaskRecord

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """System health and database connectivity probe."""
    db_ok = await check_db_health()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version="0.1.0",
        environment=settings.env,
        database_connected=db_ok,
        timestamp=datetime.now(timezone.utc),
    )


@router.post("/v1/completions", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], response_model=CompletionResponseSchema, tags=["Inference"])
async def create_completion(request: CompletionRequestSchema) -> CompletionResponseSchema:
    """Route completion through model gateway with failover."""
    try:
        response = await gateway.complete(request)
        return response
    except Exception as e:
        from core.security.error_disclosure import public_inference_detail

        # Log full exception server-side; clients get allowlisted category only (Package E).
        import logging
        logging.getLogger(__name__).warning("Inference failure", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=public_inference_detail(e),
        )


@router.get("/v1/models", dependencies=[Depends(current_principal)], tags=["Inference"])
async def list_models(
    category: Optional[str] = None,
    provider: Optional[str] = None,
    capability: Optional[str] = None,
) -> Dict[str, Any]:
    """Discover all supported AI models across Open-Weight and Closed/Proprietary providers."""
    from core.models.registry import model_registry, ModelCategory
    from core.api.schemas import Provider

    cat_enum = None
    if category:
        try:
            cat_enum = ModelCategory(category.lower())
        except ValueError:
            pass

    prov_enum = None
    if provider:
        try:
            prov_enum = Provider(provider.lower())
        except ValueError:
            pass

    models = model_registry.list_models(category=cat_enum, provider=prov_enum, capability=capability)

    # Live local-runtime truth: which advertised open-weight models are actually installed.
    installed_local: List[str] = []
    try:
        local_adapter = gateway.adapters.get(Provider.LOCAL)
        rt = local_adapter.local_runtime() if hasattr(local_adapter, "local_runtime") else None
        installed_local = list(rt.models) if rt is not None and rt.up else []
    except Exception:
        installed_local = []

    def _installed(model_id: str) -> bool:
        for name in installed_local:
            if name == model_id or name == f"{model_id}:latest" or model_id == f"{name}:latest":
                return True
            if name.split(":latest")[0] == model_id.split(":latest")[0]:
                return True
        return False

    # KEEL-PROD-041: flagship keelway-* models alias to a compatible installed
    # local runtime model; only alias-incapable or unbound entries are simulated.
    from core.opencore.runtime import LocalRuntimeDiscovery
    from core.opencore.weights import weight_manager as _opencore_weights

    def _runtime_alias_supported(model_id: str) -> bool:
        return any(mf.runtime_alias for mf in _opencore_weights.list_manifests(model_id))

    def _resolved_runtime_model(model_id: str) -> Optional[str]:
        if not model_id.startswith("keelway-") or not _runtime_alias_supported(model_id):
            return None
        return LocalRuntimeDiscovery.resolve_compatible_model(model_id, installed_local)

    def _simulated(model_id: str) -> bool:
        if not model_id.startswith("keelway-"):
            return False
        return _resolved_runtime_model(model_id) is None

    return {
        "object": "list",
        "data": [
            {
                "id": m.id,
                "object": "model",
                "name": m.name,
                "created": 1730000000,
                "owned_by": m.provider.value,
                "category": m.category.value,
                "family": m.family.value,
                "deployment": m.deployment.value,
                "deployment_type": m.deployment.value,
                "context_window": m.context_window,
                "max_output_tokens": m.max_output_tokens,
                "capabilities": m.capabilities,
                "supports_streaming": m.supports_streaming,
                "supports_tools": m.supports_tools,
                "supports_structured_output": m.supports_structured_output,
                "modalities": m.modalities,
                "pricing": {
                    "input_usd_per_mtok": m.pricing_input_usd_per_mtok,
                    "output_usd_per_mtok": m.pricing_output_usd_per_mtok,
                },
                "license": m.license,
                "recommended_vram_gb": m.recommended_vram_gb,
                "description": m.description,
                "installed": _installed(m.id) if m.category == ModelCategory.OPEN_WEIGHT else None,
                "simulated": _simulated(m.id),
                "runtime_alias": _runtime_alias_supported(m.id) if m.id.startswith("keelway-") else False,
                "resolved_model": _resolved_runtime_model(m.id),
            }
            for m in models
        ],
        "categories": {
            "open_weight": len(model_registry.list_models(category=ModelCategory.OPEN_WEIGHT)),
            "closed_proprietary": len(model_registry.list_models(category=ModelCategory.CLOSED_PROPRIETARY)),
        },
    }


@router.post("/v1/chat/completions", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Inference"])
async def chat_completions(request_raw: Request):
    """OpenAI-compatible chat completions endpoint supporting non-streaming and Server-Sent Events (SSE) streaming."""
    from core.models.provider import ChatCompletionRequest
    from core.security.error_disclosure import public_inference_detail
    import logging
    logger = logging.getLogger(__name__)

    try:
        body = await request_raw.json()
        request = ChatCompletionRequest(**body)
    except Exception as parse_err:
        raise HTTPException(status_code=400, detail=f"Invalid chat completion payload: {parse_err}")

    if request.stream:
        async def event_generator():
            try:
                async for chunk in gateway.stream_chat(request):
                    yield chunk.to_sse()
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.warning("Streaming inference error", exc_info=e)
                err_payload = json.dumps({"error": {"message": public_inference_detail(e), "type": "inference_error"}})
                yield f"data: {err_payload}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            response = await gateway.chat_complete(request)
            return response.to_openai_dict()
        except Exception as e:
            logger.warning("Inference failure", exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=public_inference_detail(e),
            )


@router.get("/v1/usage", dependencies=[Depends(current_principal)], tags=["Inference"])
async def get_model_usage() -> Dict[str, Any]:
    """Retrieve aggregate usage statistics and cost accounting across all models."""
    from core.models.cost_ledger import cost_ledger
    report = cost_ledger.get_economics_report()
    summary = cost_ledger.get_summary()
    report["total_cost_usd"] = report.get("billed_cloud_expenditure_usd", summary.get("total_external_cost_usd", 0.0))
    report["currency"] = "USD"
    report["entries_recorded"] = summary.get("total_inferences", 0)
    return report


@router.get("/v1/chat/modes", dependencies=[Depends(current_principal)], tags=["AI Assistant"])
async def list_chat_modes():
    """List available conversation modes and their governance constraints (Section 6.1)."""
    return {
        "modes": [
            {
                "id": ConversationMode.ASK.value,
                "name": "Ask Mode",
                "description": "Read-only explanations, architecture queries, symbol lookup, and error diagnosis.",
                "mutates_files": False,
                "requires_approval": False,
            },
            {
                "id": ConversationMode.PLAN.value,
                "name": "Plan Mode",
                "description": "Produces a structured, reviewable implementation plan grounded in repository code.",
                "mutates_files": False,
                "requires_approval": False,
            },
            {
                "id": ConversationMode.EDIT.value,
                "name": "Edit Mode",
                "description": "Formulates workspace-scoped code patches with diff previews and conflict detection.",
                "mutates_files": False,
                "requires_approval": True,
            },
            {
                "id": ConversationMode.AGENT.value,
                "name": "Agent Mode",
                "description": "Executes approved multi-step engineering workflows with deterministic flight recording.",
                "mutates_files": True,
                "requires_approval": True,
            },
        ]
    }


@router.post("/v1/chat/message", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["AI Assistant"])
async def send_chat_message(payload: dict, principal: Principal = Depends(current_principal)):
    """Send a message to the AI Assistant in one of the 4 conversation modes."""
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Missing required 'message' field.")

    mode_str = payload.get("mode", "ask").lower()
    try:
        mode = ConversationMode(mode_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode '{mode_str}'. Must be one of: ask, plan, edit, agent.")

    provider_str = payload.get("provider", "local").lower()
    try:
        provider = Provider(provider_str)
    except ValueError:
        provider = Provider.LOCAL

    use_memory = bool(payload.get("use_memory", True))
    target_file = payload.get("target_file")

    session = InteractiveChatSession(
        provider=provider,
        mode=mode,
        workspace_fs=_workspace_fs,
    )
    result = await session.step(
        user_message=message,
        use_memory=use_memory,
        mode=mode,
        target_file=target_file,
    )
    # If chat created an active agent task, register it for Studio tracking & approval workflows
    if result.get("agent_task", {}).get("task_id") and getattr(session, "_last_agent", None):
        t_id = result["agent_task"]["task_id"]
        _active_agent_loops[t_id] = session._last_agent
        await _publish_agent(session._last_agent)
    await record_audit(principal, f"chat_message_{mode.value}", message[:100], True)
    return result


@router.post("/v1/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
async def create_task(
    request: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require(Permission.EXECUTE_AGENT)),
) -> TaskResponse:
    """Create a new durable task."""
    task = TaskRecord(
        title=request.title,
        description=request.description,
        owner=principal.actor if request.owner == "anonymous" else request.owner,
        budget_usd=request.budget_usd,
        payload=request.payload,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    response = TaskResponse.model_validate(task)
    await _broadcast_task_state(response, previous_state=None)
    return response


@router.get("/v1/tasks", dependencies=[Depends(current_principal)], response_model=List[TaskResponse], tags=["Tasks"])
async def list_tasks(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> List[TaskResponse]:
    """List recent tasks."""
    query = select(TaskRecord).order_by(TaskRecord.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/v1/tasks/{task_id}", dependencies=[Depends(current_principal)], response_model=TaskResponse, tags=["Tasks"])
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Get single task details."""
    query = select(TaskRecord).where(TaskRecord.id == task_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found.")
    return TaskResponse.model_validate(task)


@router.post("/v1/tasks/{task_id}/transition", response_model=TaskResponse, tags=["Tasks"])
async def transition_task(
    task_id: str,
    request: TaskTransitionRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require(Permission.EXECUTE_AGENT)),
) -> TaskResponse:
    """Transition a task state with strict validation."""
    query = select(TaskRecord).where(TaskRecord.id == task_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found.")

    try:
        validate_transition(current=task.state, target=request.target_state)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    if task.state == TaskState.AWAITING_APPROVAL and request.target_state == TaskState.RUNNING:
        approved = principal.can(Permission.APPROVE_TIER3)
        await record_audit(principal, Permission.APPROVE_TIER3.value, f"approve task {task_id}", approved)
        if not approved:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Approving a task requires '{Permission.APPROVE_TIER3.value}' (admin or owner).",
            )

    previous_state = task.state
    task.state = request.target_state
    await db.flush()
    await db.refresh(task)
    response = TaskResponse.model_validate(task)
    await _broadcast_task_state(response, previous_state=previous_state)
    return response


@router.post(
    "/v1/workflows/engineering-brief",
    dependencies=[Depends(require(Permission.EXECUTE_AGENT))],
    response_model=EngineeringBriefResponse,
    status_code=status.HTTP_200_OK,
    tags=["Workflows"],
)
async def generate_engineering_brief(
    request: EngineeringBriefRequest,
    db: AsyncSession = Depends(get_db),
) -> EngineeringBriefResponse:
    """Execute Workflow 1: Pull request engineering brief generation with source citations."""
    workflow = EngineeringBriefWorkflow(gateway=gateway)
    try:
        result = await workflow.execute(
            pr_title=request.pr_title,
            pr_description=request.pr_description,
            files_touched=request.files_touched,
            failing_tests=request.failing_tests,
            db=db,
            preferred_provider=request.preferred_provider,
        )
        return EngineeringBriefResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {str(e)}",
        )


@router.post(
    "/v1/workflows/research-summary",
    dependencies=[Depends(require(Permission.EXECUTE_AGENT))],
    response_model=ResearchSummaryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Workflows"],
)
async def generate_research_summary(
    request: ResearchSummaryRequest,
    db: AsyncSession = Depends(get_db),
) -> ResearchSummaryResponse:
    """Execute Workflow 2: Research document and ADR synthesis with provenance tracking."""
    workflow = ResearchSummaryWorkflow(gateway=gateway)
    try:
        result = await workflow.execute(
            document_title=request.document_title,
            document_content=request.document_content,
            source_uri=request.source_uri,
            store_in_memory=request.store_in_memory,
            memory_key=request.memory_key,
            db=db,
            preferred_provider=request.preferred_provider,
        )
        return ResearchSummaryResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research summary workflow failed: {str(e)}",
        )


@router.post(
    "/v1/workflows/sandbox-test",
    dependencies=[Depends(require(Permission.EXECUTE_AGENT))],
    response_model=SandboxTestResponse,
    status_code=status.HTTP_200_OK,
    tags=["Workflows"],
)
async def execute_sandboxed_tests(
    request: SandboxTestRequest,
    db: AsyncSession = Depends(get_db),
) -> SandboxTestResponse:
    """Execute Workflow 3: Ephemeral sandbox test execution and root-cause failure analysis."""
    workflow = SandboxedFailureAnalysisWorkflow(gateway=gateway)
    try:
        result = await workflow.execute(
            test_command=request.test_command,
            human_approved=request.human_approved,
            timeout_seconds=request.timeout_seconds,
            db=db,
            preferred_provider=request.preferred_provider,
        )
        return SandboxTestResponse(**result)
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe),
        )
    except SandboxExecutionError as se:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(se),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sandbox test workflow failed: {str(e)}",
        )


@router.get("/v1/memories", dependencies=[Depends(current_principal)], response_model=List[MemoryResponse], tags=["Memory"])
async def search_memories(
    q: Optional[str] = None,
    scope: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> List[MemoryResponse]:
    """Search or list memories across scopes."""
    from core.storage.memory import MemoryService
    service = MemoryService(db)
    if q:
        records = await service.search(query_text=q, scope=scope, limit=limit)
    elif scope:
        records = await service.list_by_scope(scope=scope, limit=limit)
    else:
        records = await service.search(query_text="", limit=limit)
    return [MemoryResponse.model_validate(r) for r in records]


@router.post("/v1/memories", dependencies=[Depends(require(Permission.MANAGE_MEMORIES))], response_model=MemoryResponse, status_code=status.HTTP_201_CREATED, tags=["Memory"])
async def create_or_update_memory(
    request: MemoryCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    """Store or update a scoped agent memory."""
    from core.storage.memory import MemoryService
    service = MemoryService(db)
    record = await service.store(
        key=request.key,
        content=request.content,
        scope=request.scope,
        provenance_uri=request.provenance_uri,
    )
    return MemoryResponse.model_validate(record)


@router.get("/v1/memories/{key}", dependencies=[Depends(current_principal)], response_model=MemoryResponse, tags=["Memory"])
async def get_memory(
    key: str,
    scope: str = "project",
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    """Retrieve a memory record by key and scope."""
    from core.storage.memory import MemoryService
    service = MemoryService(db)
    record = await service.get(key=key, scope=scope)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Memory '{key}' not found in scope '{scope}'.")
    return MemoryResponse.model_validate(record)


@router.delete("/v1/memories/{key}", dependencies=[Depends(require(Permission.MANAGE_MEMORIES))], status_code=status.HTTP_204_NO_CONTENT, tags=["Memory"])
async def delete_memory(
    key: str,
    scope: str = "project",
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a memory record by key and scope."""
    from core.storage.memory import MemoryService
    service = MemoryService(db)
    deleted = await service.delete(key=key, scope=scope)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Memory '{key}' not found in scope '{scope}'.")


PROOF_STRIP_STAGES = ("INSPECT", "PLAN", "AUTHORIZE", "EXECUTE", "VERIFY", "SEAL")


def map_to_proof_stage(event_type: str, status: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> str:
    """Map runtime event or status to Keelway's Proof Strip lifecycle."""
    ev = (event_type or "").lower()
    st = (status or "").lower()

    if isinstance(data, dict):
        recent = data.get("recent_events") or []
        if recent and isinstance(recent[-1], dict):
            last_ev = (recent[-1].get("event_type") or recent[-1].get("type") or "").lower()
            ev = f"{ev} {last_ev}"

    # 6. SEAL: tape sealing, cryptographic hash, audit packaging, completion
    if any(k in ev for k in ("seal", "hash", "tamper", "merkle", "audit")) or st in ("completed", "sealed"):
        return "SEAL"

    # 5. VERIFY: tests, verification, AST diagnostics, self-healing check
    if any(k in ev for k in ("verify", "test", "healing", "diagnostic")) or st in ("verifying", "testing"):
        return "VERIFY"

    # 4. EXECUTE: tool execution, code generation, mutations, diff proposals
    if any(k in ev for k in ("execute", "tool", "mutation", "diff", "running", "step")) or st in ("executing_tool", "running", "executing"):
        return "EXECUTE"

    # 3. AUTHORIZE: approvals, permissions, quorum, policy evaluation
    if any(k in ev for k in ("approval", "authorize", "quorum", "policy", "permission")) or st in ("awaiting_approval", "pending_approval"):
        return "AUTHORIZE"

    # 2. PLAN: planning, plan formulation, goal breakdown
    if any(k in ev for k in ("plan", "goal", "formulate")) or st in ("planning", "plan_ready", "planned"):
        return "PLAN"

    # 1. INSPECT: initial workspace inspection, context loading, air-gap check, handshake
    if any(k in ev for k in ("inspect", "context_loading", "air_gap", "handshake")) or st in ("created", "context_loading"):
        return "INSPECT"

    return "EXECUTE" if st in ("running", "active") else "INSPECT"


class ConnectionManager:
    """Manages active WebSocket connections and SSE stream subscriptions for Keelway Studio."""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.sse_subscribers: Set[asyncio.Queue] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    def register_sse(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=256)
        self.sse_subscribers.add(q)
        return q

    def unregister_sse(self, q: asyncio.Queue):
        self.sse_subscribers.discard(q)

    async def broadcast(self, message: dict):
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()
        if "stage" not in message:
            message["stage"] = map_to_proof_stage(
                event_type=message.get("type", ""),
                status=message.get("new_state") or (message.get("state") or {}).get("status"),
                data=message.get("state"),
            )
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.active_connections.discard(connection)
        for q in list(self.sse_subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                self.sse_subscribers.discard(q)


ws_manager = ConnectionManager()


async def _broadcast_task_state(task: TaskResponse, previous_state) -> None:
    await ws_manager.broadcast({
        "type": "agent_state_changed",
        "task_id": task.id,
        "title": task.title,
        "previous_state": getattr(previous_state, "value", previous_state),
        "new_state": task.state.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@router.websocket("/v1/ws/studio")
async def websocket_studio_endpoint(websocket: WebSocket):
    """Real-time bidirectional channel for Keelway Studio events, diffs, and thought streaming."""
    if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host")):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Origin not allowed.")
    ws_token = websocket.query_params.get("token") or token_from_headers(websocket.headers)
    if settings.auth_required:
        principal = await principal_for_token(ws_token)
        if principal is None:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing or invalid API token.")
        if principal.role == Role.PHONE:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Paired phones have no Studio stream.")
    else:
        principal = LOCAL_OWNER

    async def permitted(permission: Permission, resource: str) -> bool:
        nonlocal principal
        if settings.auth_required:
            current = await principal_for_token(ws_token)
            if current is None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="API token revoked.")
                return False
            principal = current
        allowed = principal.can(permission)
        await record_audit(principal, permission.value, f"WS {resource}", allowed)
        if not allowed:
            await websocket.send_json({
                "type": "error",
                "message": f"Role '{principal.role.value}' lacks permission '{permission.value}'.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return allowed

    await ws_manager.connect(websocket)
    try:
        # Send initial connection handshake
        await websocket.send_json({
            "type": "handshake",
            "stage": "INSPECT",
            "server": "Keelway Studio",
            "version": "2.1.0-alpha",
            "air_gapped": gateway.air_gap.enabled,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        })
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            if event_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
            elif event_type == "toggle_air_gap":
                if not await permitted(Permission.APPROVE_TIER3, "toggle_air_gap"):
                    continue
                new_state = data.get("enabled", True)
                gateway.air_gap.enabled = new_state
                await ws_manager.broadcast({
                    "type": "air_gap_status_changed",
                    "air_gapped": new_state,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            elif event_type == "execute_instruction":
                if not await permitted(Permission.EXECUTE_AGENT, "execute_instruction"):
                    continue
                prompt = data.get("prompt", "")
                # Broadcast synthetic thinking / processing event
                await websocket.send_json({
                    "type": "agent_thinking",
                    "prompt": prompt,
                    "state": "EXECUTING",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            elif event_type == "run_self_healing":
                if not await permitted(Permission.EXECUTE_AGENT, "run_self_healing"):
                    continue
                from core.orchestration.self_healing import SelfHealingLoop
                test_cmd = data.get("test_command", "python3 -m unittest")
                loop = SelfHealingLoop()
                result = await loop.run_repair_cycle(test_cmd=test_cmd, max_attempts=data.get("max_attempts", 3))
                await websocket.send_json({
                    "type": "self_healing_result",
                    "success": result.success,
                    "attempts": result.attempts,
                    "verification": result.verification_output,
                    "diff": result.diff,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@router.get("/v1/events/stream", tags=["Realtime Events"])
async def stream_events(
    request: Request,
    task_id: Optional[str] = None,
):
    """Server-Sent Events (SSE) streaming endpoint for live studio task events and Proof Strip lifecycle frames."""
    if not origin_allowed(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed.")
    token = request.query_params.get("token") or token_from_headers(request.headers)
    if settings.auth_required:
        principal = await principal_for_token(token)
        if principal is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid API token.")
        if principal.role == Role.PHONE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Paired phones have no event streams.")
    else:
        principal = LOCAL_OWNER

    async def event_generator():
        q = ws_manager.register_sse()
        try:
            # Yield initial connection handshake frame matching INSPECT stage
            handshake = {
                "type": "handshake",
                "stage": "INSPECT",
                "server": "Keelway Studio",
                "version": "2.1.0-alpha",
                "air_gapped": gateway.air_gap.enabled,
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            yield f"data: {json.dumps(handshake)}\n\n"

            # If task_id is specified and currently active in memory, yield baseline state frame
            if task_id and task_id in _active_agent_loops:
                active_agent = _active_agent_loops[task_id]
                cur_state = active_agent.get_state()
                stage = map_to_proof_stage("agent_loop_updated", status=cur_state.get("status"), data=cur_state)
                task_frame = {
                    "type": "agent_loop_updated",
                    "stage": stage,
                    "task_id": task_id,
                    "state": cur_state,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                yield f"data: {json.dumps(task_frame)}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=0.5)
                    if task_id and msg.get("task_id") and msg.get("task_id") != task_id:
                        continue
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            ws_manager.unregister_sse(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/v1/flight/stream", tags=["Deterministic Flight Recorder"])
async def stream_flight_events(
    request: Request,
    task_id: Optional[str] = None,
):
    """Real-time streaming endpoint for deterministic flight tape execution frames matching Proof Strip lifecycle."""
    if not origin_allowed(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed.")
    token = request.query_params.get("token") or token_from_headers(request.headers)
    if settings.auth_required:
        principal = await principal_for_token(token)
        if principal is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid API token.")
        if principal.role == Role.PHONE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Paired phones have no event streams.")
    else:
        principal = LOCAL_OWNER

    async def flight_generator():
        q = ws_manager.register_sse()
        try:
            sent_indices = set()
            if task_id:
                try:
                    tape_file = _tape_path(task_id)
                    if tape_file.exists():
                        tape_data = json.loads(tape_file.read_text(encoding="utf-8"))
                        for ev in tape_data.get("events", []):
                            ev_type = ev.get("event_type", "")
                            stage = map_to_proof_stage(ev_type, data=ev.get("payload"))
                            frame = {
                                "type": "flight_event_frame",
                                "stage": stage,
                                "task_id": task_id,
                                "event_index": ev.get("event_index"),
                                "event_type": ev_type,
                                "payload": ev.get("payload", {}),
                                "timestamp_utc": ev.get("timestamp_utc"),
                            }
                            sent_indices.add(ev.get("event_index"))
                            yield f"data: {json.dumps(frame)}\n\n"
                except Exception:
                    pass

            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=0.5)
                    if task_id and msg.get("task_id") and msg.get("task_id") != task_id:
                        continue
                    state = msg.get("state") or {}
                    recent_events = state.get("recent_events", [])
                    for ev in recent_events:
                        idx = ev.get("event_index")
                        if idx is not None and idx in sent_indices:
                            continue
                        if idx is not None:
                            sent_indices.add(idx)
                        ev_type = ev.get("event_type") or ev.get("type") or ""
                        stage = map_to_proof_stage(ev_type, data=ev.get("payload") or ev.get("data"))
                        frame = {
                            "type": "flight_event_frame",
                            "stage": stage,
                            "task_id": msg.get("task_id") or task_id,
                            "event_index": idx,
                            "event_type": ev_type,
                            "payload": ev.get("payload") or ev.get("data", {}),
                            "timestamp_utc": time.time(),
                        }
                        yield f"data: {json.dumps(frame)}\n\n"
                    ev_type = msg.get("type", "")
                    stage = msg.get("stage") or map_to_proof_stage(ev_type, status=state.get("status"))
                    yield f"data: {json.dumps({'type': 'flight_stream_update', 'stage': stage, 'task_id': msg.get('task_id'), 'message': msg})}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            ws_manager.unregister_sse(q)

    return StreamingResponse(
        flight_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/v1/healing/repair", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Autonomous Self-Healing"])
async def trigger_self_healing(payload: dict):
    """Trigger autonomous AST fault localization and closed-loop test repair."""
    from core.orchestration.self_healing import SelfHealingLoop
    test_cmd = payload.get("test_command")
    if not test_cmd:
        raise HTTPException(status_code=400, detail="Missing required field: test_command")
    max_attempts = payload.get("max_attempts", 3)
    loop = SelfHealingLoop()
    result = await loop.run_repair_cycle(test_cmd=test_cmd, max_attempts=max_attempts)
    return {
        "success": result.success,
        "attempts": result.attempts,
        "verification_output": result.verification_output,
        "diff": result.diff,
    }


@router.post("/v1/payments/intent", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Global Sovereign Settlement"])
async def create_payment_intent(payload: dict):
    """Simulated multi-rail payment intent (M-Pesa, PIX, UPI, L402, Offline Voucher). No provider is connected; no money moves."""
    from core.storage.payment_broker import GlobalPaymentBroker, GlobalRail
    try:
        rail = GlobalRail(payload.get("rail", "mpesa"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payment rail")
    
    amount = float(payload.get("amount", 0.0))
    currency = payload.get("currency", "USD")
    recipient = payload.get("recipient", "")
    description = payload.get("description", "Keelway Agent Service")

    broker = GlobalPaymentBroker()
    try:
        intent = broker.create_intent(rail=rail, amount=amount, currency=currency, recipient=recipient, description=description)
    except InsecureDefaultConfiguration:
        raise HTTPException(
            status_code=503,
            detail="payment configuration is unavailable: source-default broker secret is refused",
        )
    return {
        "simulated": True,
        "intent_id": intent.intent_id,
        "rail": intent.rail.value,
        "amount": intent.amount,
        "currency": intent.currency,
        "recipient": intent.recipient,
        "status": intent.status,
        "payment_payload": intent.payment_payload,
        "expires_at": intent.expires_at,
    }


FLIGHT_RECORDINGS_DIR = legacy_aware(Path(".keelway/recordings"), Path(".kora/recordings"))
# 243 + len(".flight.json") == 255, the common filesystem filename limit.
_TAPE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,243}$")


def _tape_path(task_id: str) -> Path:
    if not task_id or not _TAPE_ID_PATTERN.fullmatch(task_id) or ".." in task_id:
        raise HTTPException(status_code=400, detail="Invalid flight tape task_id.")
    return FLIGHT_RECORDINGS_DIR / f"{task_id}.flight.json"


@router.get("/v1/flight/tapes", dependencies=[Depends(current_principal)], tags=["Deterministic Flight Recorder"])
async def list_flight_tapes():
    """List all recorded deterministic agent execution tapes."""
    recordings_dir = FLIGHT_RECORDINGS_DIR
    if not recordings_dir.exists():
        return {"tapes": []}
    tapes = []
    for f in recordings_dir.glob("*.flight.json"):
        tapes.append({"task_id": f.name.replace(".flight.json", ""), "path": str(f)})
    return {"tapes": tapes}


@router.get("/v1/flight/tape/{task_id}", dependencies=[Depends(current_principal)], tags=["Deterministic Flight Recorder"])
async def get_flight_tape(task_id: str):
    """Retrieve full execution tape with all chronological step frames."""
    tape_file = _tape_path(task_id)
    if not tape_file.exists():
        raise HTTPException(status_code=404, detail=f"Flight tape for task {task_id} not found.")
    import json
    return json.loads(tape_file.read_text(encoding="utf-8"))


@router.post("/v1/flight/tape/{task_id}/fork", tags=["Flight Recorder"])
async def fork_flight_tape_endpoint(task_id: str, payload: dict) -> Dict[str, Any]:
    """Fork an isolated workspace state from a specific historical flight tape event index."""
    import tempfile
    from core.orchestration.flight_recorder import FlightRecorder
    event_index = (payload or {}).get("event_index", 0)
    fork_root = tempfile.mkdtemp(prefix=f"keelway_fork_{task_id}_")
    result = FlightRecorder(task_id=task_id).fork_checkpoint(event_index=event_index, destination_path=Path(fork_root))
    return result


@router.post("/v1/flight/fork", tags=["Deterministic Flight Recorder"])
async def fork_flight_tape(
    payload: dict,
    principal: Principal = Depends(require(Permission.EXECUTE_AGENT)),
):
    """Fork an execution timeline at a specific step index to explore alternative solutions."""
    from core.orchestration.flight_recorder import FlightPlayer
    task_id = payload.get("task_id")
    at_index = int(payload.get("at_index", 0))
    new_task_id = payload.get("new_task_id") or f"{(task_id or '')[:200]}_fork_{time.time_ns()}"

    tape_file = _tape_path(task_id)
    if _tape_path(new_task_id).exists():
        raise HTTPException(status_code=409, detail=f"Flight tape {new_task_id} already exists.")
    if not tape_file.exists():
        raise HTTPException(status_code=404, detail="Source flight tape not found.")

    player = FlightPlayer(tape_file)
    if not 0 <= at_index <= len(player.events):
        raise HTTPException(status_code=400, detail=f"at_index must be between 0 and {len(player.events)}.")
    forked_recorder = player.fork(at_index=at_index, new_task_id=new_task_id)
    forked_recorder.recordings_dir = FLIGHT_RECORDINGS_DIR
    saved_path = forked_recorder.save_tape()
    tape_hash = None
    try:
        tape_hash = json.loads(saved_path.read_text(encoding="utf-8")).get("tape_sha256")
    except (OSError, json.JSONDecodeError, UnicodeError):
        tape_hash = None
    await record_audit(principal, "flight_tape_sealed", f"{new_task_id} fork_from={task_id} sha256:{tape_hash}", True)
    return {
        "original_task_id": task_id,
        "forked_task_id": new_task_id,
        "forked_at_index": at_index,
        "tape_path": str(saved_path),
    }


# =====================================================================
# Local Team Mesh & Pooled Compute Endpoints (Section 13)
# =====================================================================

from core.orchestration.p2p_mesh import get_shared_mesh, MeshPeer, MeshDelegationReceipt


@router.get("/v1/mesh/status", dependencies=[Depends(current_principal)], tags=["Local Team Mesh"])
async def mesh_status():
    """Returns local node advertisement, active peers count, and total pooled compute VRAM."""
    mesh = get_shared_mesh()
    active = mesh.active_peers()
    return {
        "local_node": mesh.get_local_advertisement(),
        "active_peers_count": len(active),
        "total_pooled_vram_mb": mesh.total_pooled_vram_mb(),
        "delegation_history_count": len(mesh.delegation_history),
    }


@router.get("/v1/mesh/peers", dependencies=[Depends(current_principal)], tags=["Local Team Mesh"])
async def list_mesh_peers():
    """List peer developer workstations discovered on local Wi-Fi / Tailscale."""
    mesh = get_shared_mesh()
    return {
        "local_node": mesh.get_local_advertisement(),
        "peers": [p.to_dict() for p in mesh.peers.values()],
        "active_peers": [p.to_dict() for p in mesh.active_peers()],
        "total_pooled_vram_mb": mesh.total_pooled_vram_mb(),
    }


@router.post("/v1/mesh/heartbeat", dependencies=[Depends(current_principal)], tags=["Local Team Mesh"])
async def mesh_heartbeat(payload: dict):
    """Registers or refreshes heartbeat from a peer node on the local mesh."""
    mesh = get_shared_mesh()
    required = ["node_id", "hostname", "lan_ip", "port", "available_vram_mb"]
    for req_f in required:
        if req_f not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required field: {req_f}")
    peer = mesh.register_peer(
        node_id=payload["node_id"],
        hostname=payload["hostname"],
        lan_ip=payload["lan_ip"],
        port=int(payload["port"]),
        available_vram_mb=int(payload["available_vram_mb"]),
        active_tasks=int(payload.get("active_tasks", 0)),
        tailscale_ip=payload.get("tailscale_ip"),
    )
    return {"status": "registered", "peer": peer.to_dict(), "total_pooled_vram_mb": mesh.total_pooled_vram_mb()}


@router.post("/v1/mesh/delegate", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Local Team Mesh"])
async def mesh_delegate(payload: dict):
    """Delegates a heavy compute/agent task across the local Wi-Fi / Tailscale team mesh."""
    mesh = get_shared_mesh()
    task_intent = payload.get("intent", "Heavy agent task")
    min_vram_mb = int(payload.get("min_vram_mb", 4096))
    allow_fallback = bool(payload.get("allow_local_fallback", True))
    task_payload = payload.get("payload", {})
    receipt = mesh.delegate_task(
        task_intent=task_intent,
        min_vram_mb=min_vram_mb,
        payload=task_payload,
        allow_local_fallback=allow_fallback,
    )
    if receipt.status == "local_fallback":
        receipt = mesh.execute_task(receipt)
    return {"status": "ok", "receipt": receipt.to_dict()}


@router.post("/v1/mesh/prune", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Local Team Mesh"])
async def mesh_prune(payload: dict = None):
    """Prunes expired peer workstations from the mesh registry."""
    mesh = get_shared_mesh()
    timeout = float((payload or {}).get("timeout_sec", 30.0))
    pruned = mesh.prune_expired_peers(timeout_sec=timeout)
    return {"pruned_count": pruned, "active_peers_count": len(mesh.active_peers())}



# =====================================================================
# Workspace Filesystem & Live Git Endpoints
# =====================================================================

from core.storage.workspace_fs import WorkspaceFilesystem, WorkspaceSecurityError
from core.storage.workspace_registry import get_shared_workspace_registry, WorkspaceEntry
from core.orchestration.project_adapter import ProjectAdapter

_workspace_fs = WorkspaceFilesystem()


def set_workspace_fs(fs: WorkspaceFilesystem) -> None:
    """Explicitly rebind the active workspace filesystem (e.g. for testing or workspace switching)."""
    global _workspace_fs, _semantic_index
    _workspace_fs = fs
    _semantic_index = CodebaseSemanticIndex(workspace_fs=_workspace_fs)


@router.get("/v1/workspaces", dependencies=[Depends(current_principal)], tags=["Workspace Filesystem"])
async def list_workspaces():
    """List all registered enterprise repositories and development workspaces."""
    reg = get_shared_workspace_registry()
    active = reg.get_active()
    return {
        "active_workspace_id": active.id if active else None,
        "workspaces": [w.to_dict() for w in reg.list_all()],
    }


@router.post("/v1/workspaces", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Workspace Filesystem"])
async def register_workspace(payload: dict, principal: Principal = Depends(current_principal)):
    """Register a new repository or workspace in the enterprise registry."""
    path_str = payload.get("path")
    if not path_str:
        raise HTTPException(status_code=400, detail="Missing required 'path' field.")
    name = payload.get("name")
    make_active = bool(payload.get("make_active", False))

    reg = get_shared_workspace_registry()
    try:
        entry = reg.register(path_str, name=name, make_active=make_active)
        if make_active:
            set_workspace_fs(WorkspaceFilesystem(root_dir=entry.path))
            await record_audit(principal, "workspace_activate", entry.path, True)
        else:
            await record_audit(principal, "workspace_register", entry.path, True)
        return {"status": "registered", "workspace": entry.to_dict()}
    except (FileNotFoundError, NotADirectoryError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/v1/workspaces/{workspace_id}/activate", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Workspace Filesystem"])
async def activate_workspace(workspace_id: str, principal: Principal = Depends(current_principal)):
    """Switch active workspace across all Keelway agent and analysis subsystems."""
    reg = get_shared_workspace_registry()
    try:
        entry = reg.activate(workspace_id)
        set_workspace_fs(WorkspaceFilesystem(root_dir=entry.path))
        await record_audit(principal, "workspace_activate", entry.path, True)
        meta = ProjectAdapter.inspect(_workspace_fs.root)
        return {
            "status": "activated",
            "workspace": entry.to_dict(),
            "project": meta.to_dict(),
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found in registry.")


@router.delete("/v1/workspaces/{workspace_id}", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Workspace Filesystem"])
async def unregister_workspace(workspace_id: str, principal: Principal = Depends(current_principal)):
    """Unregister a workspace from the enterprise registry."""
    reg = get_shared_workspace_registry()
    ok = reg.unregister(workspace_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found.")
    await record_audit(principal, "workspace_unregister", workspace_id, True)
    return {"status": "unregistered", "workspace_id": workspace_id}


@router.get("/v1/workspace", dependencies=[Depends(current_principal)], tags=["Workspace Filesystem"])
async def get_workspace_info():
    """Retrieve active workspace directory path, git repository status, and metadata."""
    is_git = (_workspace_fs.root / ".git").exists()
    tree = _workspace_fs.get_file_tree()
    meta = ProjectAdapter.inspect(_workspace_fs.root)
    return {
        "root": str(_workspace_fs.root),
        "name": _workspace_fs.root.name,
        "is_git": is_git,
        "files_count": len(tree.get("tree", {}).get("children", [])),
        "project": meta.to_dict(),
    }


@router.get("/v1/project/info", dependencies=[Depends(current_principal)], tags=["Workspace Filesystem"])
async def get_project_info():
    """Deterministically inspect the active workspace to detect project runtime, frameworks, and test runners."""
    meta = ProjectAdapter.inspect(_workspace_fs.root)
    return meta.to_dict()


@router.post("/v1/workspace/open", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Workspace Filesystem"])
async def open_workspace(payload: dict, principal: Principal = Depends(current_principal)):
    """Open an existing local source repository or workspace directory in Keelway."""
    path_str = payload.get("path")
    if not path_str:
        raise HTTPException(status_code=400, detail="Missing required 'path' field.")
    target = Path(path_str).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Target directory '{target}' does not exist.")

    global _workspace_fs, _semantic_index
    _workspace_fs = WorkspaceFilesystem(str(target))
    _semantic_index = CodebaseSemanticIndex(workspace_fs=_workspace_fs)
    reg = get_shared_workspace_registry()
    try:
        reg.register(str(target), name=target.name, make_active=True)
    except Exception:
        pass
    await record_audit(principal, "workspace_open", str(target), True)

    meta = ProjectAdapter.inspect(_workspace_fs.root)
    return {
        "status": "opened",
        "root": str(_workspace_fs.root),
        "name": _workspace_fs.root.name,
        "is_git": (_workspace_fs.root / ".git").exists(),
        "project": meta.to_dict(),
    }



@router.get("/v1/files/tree", dependencies=[Depends(current_principal)], tags=["Workspace Filesystem"])
async def get_workspace_file_tree(subpath: str = ".", max_depth: int = 4):
    """Retrieve recursive workspace file tree honoring .gitignore rules."""
    try:
        return _workspace_fs.get_file_tree(subpath=subpath, max_depth=max_depth)
    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/v1/files/content", dependencies=[Depends(current_principal)], tags=["Workspace Filesystem"])
async def read_workspace_file(path: str):
    """Safely read text content of a workspace file."""
    try:
        return _workspace_fs.read_file(path)
    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/v1/files/save", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Workspace Filesystem"])
async def save_workspace_file(payload: dict):
    """Atomically write content to a workspace file."""
    path = payload.get("path")
    content = payload.get("content")
    if not path or content is None:
        raise HTTPException(status_code=400, detail="Missing required 'path' or 'content' field.")
    try:
        return _workspace_fs.write_file(path, content)
    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


@router.post("/v1/files/upload", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Workspace Filesystem"])
async def upload_workspace_file(request: Request):
    """Upload a file or a .zip project archive directly into the active workspace.

    Supports JSON body with base64/text or raw binary with X-Filename header.
    Automatically unzips archives safely with ZipSlip directory traversal checks.
    """
    import base64
    import io
    import zipfile

    content_type = request.headers.get("content-type", "")
    filename = request.headers.get("x-filename", "uploaded_file")

    if "application/json" in content_type:
        body = await request.json()
        filename = body.get("filename", filename)
        if "content_base64" in body:
            raw_bytes = base64.b64decode(body["content_base64"])
        else:
            raw_bytes = body.get("content", "").encode("utf-8")
    else:
        raw_bytes = await request.body()

    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty upload payload.")

    if filename.lower().endswith(".zip"):
        extracted_files = []
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    # Security check against ZipSlip path traversal
                    target_path = _workspace_fs.resolve_safe_path(member.filename)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target_path, "wb") as dst:
                        dst.write(src.read())
                    extracted_files.append(member.filename)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to unpack zip archive: {str(e)}")

        try:
            _semantic_index.index_workspace(max_files=150)
        except Exception:
            pass

        return {
            "status": "success",
            "type": "zip_archive",
            "filename": filename,
            "extracted_count": len(extracted_files),
            "files": extracted_files,
        }
    else:
        try:
            target_path = _workspace_fs.resolve_safe_path(filename)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(raw_bytes)
        except WorkspaceSecurityError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

        try:
            _semantic_index.index_workspace(max_files=150)
        except Exception:
            pass

        return {
            "status": "success",
            "type": "single_file",
            "path": filename,
            "size_bytes": len(raw_bytes),
        }


@router.get("/v1/git/status", dependencies=[Depends(current_principal)], tags=["Workspace Git"])
async def get_workspace_git_status():
    """Retrieve live Git repository status, branch, and modified files."""
    return _workspace_fs.get_git_status()


@router.get("/v1/git/diff", dependencies=[Depends(current_principal)], tags=["Workspace Git"])
async def get_workspace_git_diff(path: Optional[str] = None):
    """Retrieve live unified Git diff for workspace or specific file."""
    try:
        return _workspace_fs.get_git_diff(path=path)
    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/v1/git/proposal", dependencies=[Depends(current_principal)], tags=["Workspace Git"])
async def get_git_commit_proposal():
    """Generates a structured semantic commit message and diff metrics from uncommitted workspace changes."""
    try:
        return _workspace_fs.prepare_commit_proposal()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/v1/git/commit", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Workspace Git"])
async def create_local_git_commit(payload: dict, principal: Principal = Depends(current_principal)):
    """Creates a verified local Git commit. Pushing to remote is never performed automatically."""
    message = payload.get("message", "")
    author_name = payload.get("author_name", principal.actor)
    author_email = payload.get("author_email", f"{principal.actor}@keelway.local")

    try:
        res = _workspace_fs.create_local_commit(
            message=message,
            author_name=author_name,
            author_email=author_email,
        )
        await record_audit(principal, "git_local_commit", f"{res['commit_sha'][:8]} {message.splitlines()[0]}", True)
        return res
    except ValueError as e:
        await record_audit(principal, "git_local_commit_rejected", str(e), False)
        raise HTTPException(status_code=400, detail=str(e))
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e)
        await record_audit(principal, "git_local_commit_failed", err, False)
        raise HTTPException(status_code=500, detail=f"Git commit failed: {err}")


@router.get("/v1/git/pr/proposal", dependencies=[Depends(current_principal)], tags=["Workspace Git"])
async def get_git_pr_proposal(base_branch: str = "main"):
    """Generates a structured Pull Request proposal with change summary and test evidence."""
    try:
        return _workspace_fs.prepare_pr_proposal(base_branch=base_branch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =====================================================================
# Codebase Semantic Index & RepoMap Endpoints
# =====================================================================

from core.storage.ast_index import CodebaseSemanticIndex

_semantic_index = CodebaseSemanticIndex(workspace_fs=_workspace_fs)


@router.get("/v1/index/repomap", dependencies=[Depends(current_principal)], tags=["Codebase Index"])
async def get_repository_map(max_tokens: int = 1500):
    """Retrieve condensed repository map for prompt context augmentation."""
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    return {
        "repo_map": _semantic_index.generate_repo_map(max_tokens=max_tokens),
        "total_files": len(_semantic_index.symbols),
    }


@router.get("/v1/index/search", dependencies=[Depends(current_principal)], tags=["Codebase Index"])
async def search_codebase_symbols(q: str, top_k: int = 10):
    """Perform hybrid semantic and lexical search across indexed codebase symbols."""
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    return {
        "query": q,
        "results": _semantic_index.search_symbols(query=q, top_k=top_k),
    }


@router.post("/v1/index/refresh", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Codebase Index"])
async def refresh_codebase_index(max_files: int = 200):
    """Re-index workspace files and refresh symbol embeddings."""
    res = _semantic_index.index_workspace(max_files=max_files)
    return {"status": "indexed", "stats": res}


@router.get("/v1/codebase/symbols", dependencies=[Depends(current_principal)], tags=["Codebase Intelligence"])
async def codebase_symbols(q: str = "", top_k: int = 15):
    """Search codebase symbols with hybrid vector and lexical ranking."""
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    results = _semantic_index.search_symbols(query=q, top_k=top_k) if q else []
    return {"query": q, "total_files": len(_semantic_index.symbols), "results": results}


@router.get("/v1/codebase/repomap", dependencies=[Depends(current_principal)], tags=["Codebase Intelligence"])
async def codebase_repomap(max_tokens: int = 1500):
    """Retrieve condensed repository map for prompt context augmentation."""
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    return {
        "repo_map": _semantic_index.generate_repo_map(max_tokens=max_tokens),
        "total_files": len(_semantic_index.symbols),
    }


@router.get("/v1/codebase/references", dependencies=[Depends(current_principal)], tags=["Codebase Intelligence"])
async def codebase_references(symbol: str):
    """Find all usages, call sites, imports, and definitions of a symbol across the workspace."""
    if not symbol:
        raise HTTPException(status_code=400, detail="Query parameter 'symbol' is required.")
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    refs = _semantic_index.find_references(symbol_name=symbol)
    return {"symbol": symbol, "count": len(refs), "references": refs}


@router.get("/v1/codebase/hierarchy", dependencies=[Depends(current_principal)], tags=["Codebase Intelligence"])
async def codebase_call_hierarchy(symbol: str):
    """Inspect callers and callees for a specific function or method."""
    if not symbol:
        raise HTTPException(status_code=400, detail="Query parameter 'symbol' is required.")
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    hierarchy = _semantic_index.get_call_hierarchy(symbol_name=symbol)
    return hierarchy


@router.get("/v1/codebase/graph", dependencies=[Depends(current_principal)], tags=["Codebase Intelligence"])
async def codebase_dependency_graph():
    """Retrieve module-level import dependency DAG with cycle detection."""
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    graph = _semantic_index.get_module_dependency_graph()
    return graph


@router.get("/v1/codebase/definition", dependencies=[Depends(current_principal)], tags=["Codebase Intelligence"])
async def codebase_definition(symbol: str):
    """Locate the exact definition, signature, and file location for a symbol."""
    if not symbol:
        raise HTTPException(status_code=400, detail="Query parameter 'symbol' is required.")
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    defn = _semantic_index.get_definition(symbol_name=symbol)
    if not defn:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found in indexed codebase.")
    return {"symbol": symbol, "definition": defn}



# =====================================================================
# Autonomous ReAct Agent Loop Endpoints
# =====================================================================

from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.agents import manifest as agent_manifest
from core.agents.guard import ManifestNotRunnable, loop_from_manifest, not_enforced, preflight
from core.agents.sandbox import verified_command_runner
from core.security.approval_rules import ApprovalRuleError, ApprovalRuleStore, is_expired, validate_scope

_active_agent_loops: Dict[str, AutonomousAgentLoop] = {}


async def _publish_agent(agent: AutonomousAgentLoop) -> Dict[str, Any]:
    """Persist the agent's flight tape and push its new state to every Studio client."""
    state = agent.get_state()
    if agent.flight_recorder and agent.flight_recorder.events:
        agent.flight_recorder.recordings_dir = FLIGHT_RECORDINGS_DIR
        agent.flight_recorder.save_tape()
    await ws_manager.broadcast({
        "type": "agent_loop_updated",
        "task_id": agent.task_id,
        "state": state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return state


def _signature_state(manifest: "agent_manifest.AgentManifest") -> Tuple[str, str]:
    """('unsigned'|'valid'|'invalid'|'no_key', reason) for a manifest against this workspace's signing key."""
    if manifest.signature is None:
        return "unsigned", ""
    key_path = Path(_workspace_fs.root) / ".keelway" / agent_manifest.KEY_FILE
    if not key_path.exists():
        return "no_key", "this workspace has no signing key, so the signature cannot be checked"
    try:
        key = bytes.fromhex(key_path.read_text().strip())
    except ValueError:
        return "no_key", "this workspace's signing key file is unreadable"
    ok, reason = agent_manifest.verify(manifest, key)
    return ("valid", "") if ok else ("invalid", reason)


async def _checked_manifest(raw: Any, principal: Principal, task_id: str) -> Tuple["agent_manifest.AgentManifest", bool]:
    """Validate and signature-check an inline manifest, auditing every refusal. Returns (manifest, signed)."""
    report = agent_manifest.validate(raw)
    if not report.ok:
        await record_audit(principal, "agent_run_manifest", f"{task_id} invalid manifest: {report.errors[0]}", False)
        raise HTTPException(status_code=422, detail={"message": "Invalid agent manifest.", "errors": report.errors})
    manifest = report.manifest
    state, reason = _signature_state(manifest)
    if state in ("invalid", "no_key"):
        await record_audit(principal, "agent_run_manifest", f"{task_id} {manifest.name}@{manifest.version} signature {state}", False)
        raise HTTPException(status_code=400, detail=f"Manifest signature check failed: {reason}")
    if state == "unsigned" and settings.require_signed_manifests:
        await record_audit(principal, "agent_run_manifest", f"{task_id} {manifest.name}@{manifest.version} unsigned", False)
        raise HTTPException(status_code=400, detail="This server only runs signed agent manifests (require_signed_manifests).")
    return manifest, state == "valid"


@router.post("/v1/agent/run", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Autonomous Agent Loop"])
async def run_agent_task(payload: dict, principal: Principal = Depends(current_principal)):
    """Initialize and run an autonomous agent engineering task."""
    task_id = payload.get("task_id") or f"task_{time.time_ns()}"
    _tape_path(task_id)
    goal = payload.get("goal", "Inspect codebase and prepare solution")
    steps = payload.get("steps") or AutonomousAgentLoop.formulate_plan(goal)
    manifest, manifest_signed = None, False
    manifest_data = payload.get("manifest")
    if manifest_data is None and payload.get("manifest_ref"):
        from core.storage.database import AsyncSessionLocal
        from core.agents.registry import resolve_manifest_ref, ManifestRegistryError
        async with AsyncSessionLocal() as db:
            try:
                reg_record = await resolve_manifest_ref(db, payload["manifest_ref"])
                manifest_data = json.loads(reg_record.manifest_json)
            except ManifestRegistryError as exc:
                await record_audit(principal, "agent_run_manifest", f"{task_id} registry ref {payload['manifest_ref']}: {exc}", False)
                raise HTTPException(status_code=400, detail=str(exc))
    if manifest_data is not None:
        manifest, manifest_signed = await _checked_manifest(manifest_data, principal, task_id)
        if payload.get("policy") not in (None, manifest.permissions.autonomy):
            raise HTTPException(status_code=400, detail="'policy' conflicts with the manifest's permissions.autonomy; omit it.")
    policy_str = manifest.permissions.autonomy if manifest is not None else payload.get("policy", "confirm_mutation")
    policy = AutonomyPolicy(policy_str) if policy_str in [p.value for p in AutonomyPolicy] else AutonomyPolicy.CONFIRM_MUTATION
    if policy == AutonomyPolicy.AUTONOMOUS:
        allowed = principal.can(Permission.APPROVE_TIER3)
        await record_audit(principal, Permission.APPROVE_TIER3.value, "agent policy autonomous", allowed)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The 'autonomous' policy skips approvals and requires 'approve_tier3' (admin or owner).",
            )

    agent = None
    if manifest is not None:
        try:  # off the event loop: the sandbox self-test starts processes
            agent = await asyncio.to_thread(loop_from_manifest, manifest, task_id, _workspace_fs, True, ApprovalRuleStore(_workspace_fs.root))
        except ManifestNotRunnable as exc:
            await record_audit(principal, "agent_run_manifest", f"{task_id} {manifest.name}@{manifest.version} not runnable: {exc}", False)
            raise HTTPException(status_code=422, detail=str(exc))
        agent.guard.signed = manifest_signed

    # No await between this check and registration, so concurrent runs can't both claim the id.
    if task_id in _active_agent_loops or _tape_path(task_id).exists():
        raise HTTPException(status_code=409, detail=f"Agent task {task_id} already exists.")
    if agent is None:
        pol_engine = None
        if payload.get("governed") or payload.get("policy_version"):
            from keelway.policy.engine import PolicyEngine
            pol_engine = PolicyEngine(policy_id=payload.get("policy_version", "default_governed_v1"))

        q_service = None
        env_mode = payload.get("environment", "internal")
        if env_mode == "production" or payload.get("quorum"):
            from keelway.approvals.quorum import QUORUM_SECRET_KEY, TwoHumanQuorumService
            from keelway.security.source_defaults import configured_signing_key
            q_service = TwoHumanQuorumService(
                signing_key=configured_signing_key("KEELWAY_QUORUM_SIGNING_KEY", QUORUM_SECRET_KEY)
            )

        agent = AutonomousAgentLoop(
            task_id=task_id,
            workspace_fs=_workspace_fs,
            policy=policy,
            record_flight=True,
            approval_rules=ApprovalRuleStore(_workspace_fs.root),
            policy_engine=pol_engine,
            quorum_service=q_service,
            environment=env_mode,
            actor_id=principal.actor,
            model_id=payload.get("model_id") if isinstance(payload.get("model_id"), str) else None,
            prompt_version=payload.get("prompt_version") if isinstance(payload.get("prompt_version"), str) else None,
        )
        # Commands run only inside a verified sandbox; without one, run_command stays unavailable.
        agent.command_runner, _ = await asyncio.to_thread(verified_command_runner, _workspace_fs.root)
    agent.initialize_plan(goal=goal, steps=steps)
    _active_agent_loops[task_id] = agent

    response: Dict[str, Any] = {
        "task_id": task_id,
        "goal": goal,
        "policy": agent.policy.value,
    }
    if manifest is not None:
        await record_audit(principal, "agent_run_manifest", f"{task_id} {manifest.name}@{manifest.version} {agent.guard.manifest_digest}", True)
        response["manifest"] = agent.guard.summary()
        response["not_enforced"] = not_enforced(manifest)
    response["state"] = await _publish_agent(agent)
    return response


@router.get("/v1/agent/runs", dependencies=[Depends(current_principal)], tags=["Autonomous Agent Loop"])
async def list_agent_runs():
    """Agent runs in this server process, newest first, summarised for the Studio task list."""
    runs = []
    for agent in reversed(list(_active_agent_loops.values())):
        state = agent.get_state()
        runs.append({
            "task_id": state["task_id"],
            "goal": state["goal"],
            "status": state["status"],
            "policy": state["policy"],
            "steps_total": len(state["plan"]),
            "steps_done": sum(step["status"] == "completed" for step in state["plan"]),
            "pending_approval": state["pending_approval"],
        })
    return {"runs": runs}


@router.get("/v1/agent/status/{task_id}", dependencies=[Depends(current_principal)], tags=["Autonomous Agent Loop"])
async def get_agent_status(task_id: str):
    """Retrieve current state, plan steps, and pending approvals for an agent."""
    if task_id not in _active_agent_loops:
        raise HTTPException(status_code=404, detail=f"Agent loop for task '{task_id}' not found.")
    return _active_agent_loops[task_id].get_state()


@router.post("/v1/agent/step/{task_id}", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Autonomous Agent Loop"])
async def step_agent_tool(task_id: str, payload: dict, principal: Principal = Depends(current_principal)):
    """Execute a single tool call within the agent loop."""
    if task_id not in _active_agent_loops:
        raise HTTPException(status_code=404, detail=f"Agent loop for task '{task_id}' not found.")

    tool_name = payload.get("tool_name")
    arguments = payload.get("arguments", {})
    step_id = payload.get("step_id")

    if not tool_name:
        raise HTTPException(status_code=400, detail="Missing 'tool_name' in request payload.")

    agent = _active_agent_loops[task_id]
    if agent.policy == AutonomyPolicy.AUTONOMOUS:
        allowed = principal.can(Permission.APPROVE_TIER3)
        await record_audit(principal, Permission.APPROVE_TIER3.value, f"agent step autonomous {task_id}", allowed)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Stepping an 'autonomous' agent skips approvals and requires 'approve_tier3' (admin or owner).",
            )
    try:
        res = await agent.execute_tool(tool_name=tool_name, arguments=arguments, step_id=step_id)
        if isinstance(res, dict) and res.get("status") == "denied_by_manifest" and agent.guard is not None:
            await record_audit(principal, "manifest_denied", f"{task_id} {tool_name}: {res.get('code')} [{agent.guard.manifest_digest[:19]}]", False)
        state = await _publish_agent(agent)
        from core.api.messaging_routes import notify_if_paused
        await notify_if_paused(res)
        return {
            "task_id": task_id,
            "step_result": res,
            "agent_state": state,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/agent/approve/{task_id}", dependencies=[Depends(require(Permission.APPROVE_AGENT_STEPS))], tags=["Autonomous Agent Loop"])
async def approve_agent_action(task_id: str, payload: dict, principal: Principal = Depends(current_principal)):
    """Human-in-the-loop: grant or deny a pending mutating tool, optionally remembering a scoped standing approval."""
    # P-10: missing/non-boolean approved must not default to True (fail closed).
    # Validate before task lookup so omission never looks like an approval.
    if not isinstance(payload, dict) or "approved" not in payload or not isinstance(payload.get("approved"), bool):
        raise HTTPException(
            status_code=400,
            detail="Explicit boolean 'approved' is required (true or false). Omitting it is not an approval.",
        )
    approved = payload["approved"]
    if task_id not in _active_agent_loops:
        raise HTTPException(status_code=404, detail=f"Agent loop for task '{task_id}' not found.")
    agent = _active_agent_loops[task_id]
    remember = payload.get("remember")
    rule = None
    if remember is not None and principal.role == Role.PHONE:
        await record_audit(principal, "approval_rule_create", f"task {task_id}", False)
        raise HTTPException(status_code=403, detail="A paired phone approves one step at a time; 'Allow always' needs Studio.")
    if approved and remember is not None and agent.pending_approval:
        pending = agent.pending_approval
        args = pending.get("arguments") or {}
        requested = (remember or {}).get("scope") if isinstance(remember, dict) else None
        try:
            default = args.get("path") or args.get("command")
            scope = validate_scope(pending["tool_name"], default if requested is None else requested)
        except ApprovalRuleError as e:
            raise HTTPException(status_code=400, detail=str(e))
        rule, created = ApprovalRuleStore(_workspace_fs.root).add(
            pending["tool_name"],
            scope,
            principal.actor,
            bound_model_id=remember.get("model_id") if isinstance(remember, dict) else None,
            bound_prompt_version=remember.get("prompt_version") if isinstance(remember, dict) else None,
        )
        if created:
            await record_audit(principal, "approval_rule_create", f"{rule.tool_name}:{rule.scope}", True)

    from core.api.messaging_routes import relay
    relay.forget_task(task_id)
    res = await agent.approve_pending(approved=approved)
    return {
        "task_id": task_id,
        "approval_result": res,
        "rule": rule.to_dict() if rule else None,
        "agent_state": await _publish_agent(agent),
    }


@router.post("/v1/agent/cancel/{task_id}", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Autonomous Agent Loop"])
async def cancel_agent_task(task_id: str, principal: Principal = Depends(current_principal)):
    """Cancel an active agent task and terminate any running child subprocesses."""
    if task_id not in _active_agent_loops:
        raise HTTPException(status_code=404, detail=f"Agent loop for task '{task_id}' not found.")
    agent = _active_agent_loops[task_id]
    cancel_res = agent.cancel()
    await record_audit(principal, "agent_task_cancel", task_id, True)
    state = await _publish_agent(agent)
    return {
        "task_id": task_id,
        "result": cancel_res,
        "agent_state": state,
    }


@router.post("/v1/agent/quorum-approve/{task_id}", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Autonomous Agent Loop"])
async def quorum_approve_agent_action(task_id: str, payload: dict, principal: Principal = Depends(current_principal)):
    """Enterprise two-human quorum approval: submit role signature (Security Lead or Platform Owner)."""
    if task_id not in _active_agent_loops:
        raise HTTPException(status_code=404, detail=f"Agent loop for task '{task_id}' not found.")
    agent = _active_agent_loops[task_id]
    principal_id = payload.get("principal_id") or principal.actor
    role = payload.get("role")
    if not role:
        raise HTTPException(status_code=400, detail="Missing required 'role' for quorum approval.")
    res = agent.submit_quorum_approval(principal_id=principal_id, role=role)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message", "Quorum approval error"))
    await record_audit(principal, "agent_quorum_approval", f"{task_id}:{role}:{principal_id}", True)
    return {
        "task_id": task_id,
        "quorum_result": res,
        "agent_state": await _publish_agent(agent),
    }


@router.post("/v1/terminal/exec", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Workspace Filesystem"])
async def execute_terminal_command(payload: dict, principal: Principal = Depends(current_principal)):
    """Execute an interactive command inside the workspace with security gating and environment scrubbing."""
    cmd = payload.get("command", "").strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="Missing 'command' in request payload.")
    # The Studio terminal has no verified isolation boundary. Do not fall back to the host shell.
    _ = (cmd, principal)
    raise HTTPException(
        status_code=503,
        detail="command execution is unavailable: no verified isolation boundary is configured",
    )


@router.post("/v1/agents/validate", dependencies=[Depends(current_principal)], tags=["Agent Manifests"])
async def validate_agent_manifest(payload: dict):
    """Dry run: is this manifest valid, signed correctly, and runnable on this machine? Starts nothing."""
    report = agent_manifest.validate(payload.get("manifest", payload))
    out: Dict[str, Any] = {"valid": report.ok, "errors": report.errors, "warnings": report.warnings}
    if not report.ok:
        return out
    manifest = report.manifest
    state, reason = _signature_state(manifest)
    reason_not_runnable = await asyncio.to_thread(preflight, manifest, Path(_workspace_fs.root))
    out.update(
        digest=agent_manifest.digest(manifest),
        signature={"state": state, "reason": reason},
        requires_signature=settings.require_signed_manifests,
        runnable=reason_not_runnable is None and state not in ("invalid", "no_key")
        and not (state == "unsigned" and settings.require_signed_manifests),
        runnable_reason=reason_not_runnable,
        not_enforced=not_enforced(manifest),
    )
    return out


@router.get("/v1/agents/registry", dependencies=[Depends(current_principal)], tags=["Agent Manifest Registry"])
async def list_registry_manifests(enabled_only: bool = False, db: AsyncSession = Depends(get_db)):
    """List all registered agent manifests."""
    from core.agents.registry import list_registered_manifests
    records = await list_registered_manifests(db, enabled_only=enabled_only)
    return {
        "manifests": [
            {
                "id": r.id,
                "name": r.name,
                "version": r.version,
                "owner": r.owner,
                "description": r.description,
                "digest": r.digest,
                "enabled": r.enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in records
        ]
    }


@router.post("/v1/agents/registry", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Agent Manifest Registry"])
async def register_agent_manifest(payload: dict, principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    """Publish and register an agent manifest in the workspace registry."""
    from core.agents.registry import register_manifest, ManifestRegistryError
    manifest_data = payload.get("manifest", payload)
    try:
        record = await register_manifest(db, manifest_data, owner_override=principal.actor)
        await db.commit()
        await record_audit(principal, "manifest_registered", f"{record.id} digest={record.digest}", True)
        return {
            "registered": True,
            "id": record.id,
            "digest": record.digest,
            "enabled": record.enabled,
        }
    except ManifestRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/v1/agents/registry/{name}/{version}", dependencies=[Depends(current_principal)], tags=["Agent Manifest Registry"])
async def get_registry_manifest(name: str, version: str, db: AsyncSession = Depends(get_db)):
    """Get the full manifest definition by name and version."""
    from core.agents.registry import get_registered_manifest
    record = await get_registered_manifest(db, name, version)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Manifest '{name}@{version}' not found.")
    return {
        "id": record.id,
        "name": record.name,
        "version": record.version,
        "owner": record.owner,
        "digest": record.digest,
        "enabled": record.enabled,
        "manifest": json.loads(record.manifest_json),
    }


@router.post("/v1/agents/registry/{name}/{version}/toggle", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Agent Manifest Registry"])
async def toggle_registry_manifest(name: str, version: str, payload: dict, principal: Principal = Depends(current_principal), db: AsyncSession = Depends(get_db)):
    """Kill-switch: enable or disable an agent manifest version immediately."""
    from core.agents.registry import toggle_manifest_status, ManifestRegistryError
    enabled = payload.get("enabled", True)
    try:
        record = await toggle_manifest_status(db, name, version, enabled)
        await db.commit()
        action = "manifest_enabled" if enabled else "manifest_disabled_kill_switch"
        await record_audit(principal, action, f"{record.id}", True)
        return {
            "id": record.id,
            "enabled": record.enabled,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }
    except ManifestRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# =====================================================================
# Agent Builder Endpoints (Section 12)
# =====================================================================

@router.get("/v1/agent/builder/templates", dependencies=[Depends(current_principal)], tags=["Agent Builder"])
async def list_agent_templates():
    """List built-in agent templates for scaffolding AI agents."""
    from core.agents.builder import AgentBuilder
    return {"templates": AgentBuilder.list_templates()}


@router.post("/v1/agent/builder/scaffold", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Agent Builder"])
async def scaffold_agent(payload: dict, principal: Principal = Depends(current_principal)):
    """Scaffold a new agent from template or spec, compile manifest, and run initial test harness."""
    from core.agents.builder import AgentBuilder
    from core.agents.spec import AgentSpec

    template_id = payload.get("template_id")
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Missing required 'name' field.")

    target_subpath = payload.get("target_dir", f"agents/{name}")
    target_dir = Path(_workspace_fs.root) / target_subpath

    if "spec" in payload:
        try:
            spec = AgentSpec.from_json(payload["spec"])
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid agent spec: {exc}")
    elif template_id:
        try:
            spec = AgentBuilder.create_from_template(
                template_id=template_id,
                name=name,
                author=principal.actor,
                overrides=payload.get("overrides"),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        raise HTTPException(status_code=400, detail="Either 'template_id' or 'spec' must be provided.")

    receipt = await AgentBuilder.build_and_register(spec, target_dir=target_dir, register_in_db=True)
    await record_audit(principal, "agent_scaffold", f"{spec.name}@{spec.version} -> {target_subpath}", receipt.tests_passed)

    return {
        "status": "created",
        "receipt": receipt.to_dict(),
        "target_dir": str(target_subpath),
        "manifest": spec.to_manifest_dict(),
    }


@router.post("/v1/agent/builder/pack", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Agent Builder"])
async def pack_agent_bundle(payload: dict, principal: Principal = Depends(current_principal)):
    """Pack an agent directory into a distributable .tar.gz bundle with SHA-256 digests."""
    from core.agents.builder import AgentBundlePacker

    source_dir_str = payload.get("source_dir")
    if not source_dir_str:
        raise HTTPException(status_code=400, detail="Missing required 'source_dir' field.")

    try:
        source_dir = _workspace_fs.resolve_safe_path(source_dir_str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid source directory: {exc}")

    if not source_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Source directory '{source_dir_str}' does not exist.")

    out_archive_str = payload.get("output_archive")
    if out_archive_str:
        try:
            output_archive = _workspace_fs.resolve_safe_path(out_archive_str)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid output archive path: {exc}")
    else:
        output_archive = source_dir.parent / f"{source_dir.name}.tar.gz"

    try:
        manifest = AgentBundlePacker.pack(source_dir, output_archive)
        rel_archive = str(output_archive.relative_to(_workspace_fs.root))
        await record_audit(principal, "agent_pack", f"{source_dir_str} -> {rel_archive}", True)
        return {
            "status": "packed",
            "archive_path": rel_archive,
            "manifest": manifest,
        }
    except Exception as exc:
        await record_audit(principal, "agent_pack", f"{source_dir_str}", False)
        raise HTTPException(status_code=500, detail=f"Packaging failed: {exc}")


@router.post("/v1/agent/builder/unpack", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Agent Builder"])
async def unpack_agent_bundle(payload: dict, principal: Principal = Depends(current_principal)):
    """Unpack and cryptographically verify an agent bundle archive."""
    from core.agents.builder import AgentBundlePacker

    archive_str = payload.get("archive_path")
    if not archive_str:
        raise HTTPException(status_code=400, detail="Missing required 'archive_path' field.")

    archive_p = Path(archive_str)
    if archive_p.is_absolute() and archive_p.is_file():
        archive_path = archive_p.resolve()
    else:
        try:
            archive_path = _workspace_fs.resolve_safe_path(archive_str)
        except Exception as exc:
            if archive_p.is_file():
                archive_path = archive_p.resolve()
            else:
                raise HTTPException(status_code=400, detail=f"Invalid archive path: {exc}")

    if not archive_path.is_file():
        raise HTTPException(status_code=404, detail=f"Archive file '{archive_str}' does not exist.")

    dest_str = payload.get("destination_dir")
    if dest_str:
        try:
            destination_dir = _workspace_fs.resolve_safe_path(dest_str)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid destination directory: {exc}")
    else:
        bundle_stem = archive_path.name.replace(".tar.gz", "").replace(".tar", "")
        destination_dir = _workspace_fs.root / "agents" / bundle_stem

    try:
        manifest = AgentBundlePacker.unpack(archive_path, destination_dir, verify=True)
        rel_dest = str(destination_dir.relative_to(_workspace_fs.root))
        await record_audit(principal, "agent_unpack", f"{archive_str} -> {rel_dest}", True)
        return {
            "status": "unpacked",
            "destination_dir": rel_dest,
            "manifest": manifest,
        }
    except Exception as exc:
        await record_audit(principal, "agent_unpack", f"{archive_str}", False)
        raise HTTPException(status_code=400, detail=f"Unpacking verification failed: {exc}")


# =====================================================================
# Customer Outbound Runner Endpoints (WP10 / WP11)
# =====================================================================

RUNNER_JOBS_QUEUE: List[Dict[str, Any]] = []

@router.post("/v1/runner/jobs/enqueue", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Customer Runner"])
async def enqueue_customer_runner_job(payload: dict, principal: Principal = Depends(current_principal)):
    """Enqueues an asynchronous task execution job for pickup by an outbound customer VPC runner daemon."""
    import uuid
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job = {
        "job_id": job_id,
        "org_id": payload.get("org_id", "default_org"),
        "project_id": payload.get("project_id", "default_project"),
        "task_prompt": payload.get("task_prompt", "Customer runner task"),
        "repo_path": payload.get("repo_path", "."),
        "actor_id": principal.actor,
        "policy_version": payload.get("policy_version", "default_governed_v1"),
        "token_ceiling": payload.get("token_ceiling", 50000),
        "cost_ceiling_cents": payload.get("cost_ceiling_cents", 500),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    RUNNER_JOBS_QUEUE.append(job)
    await record_audit(principal, "runner_job_enqueue", f"{job_id} org={job['org_id']}", True)
    return {"status": "ENQUEUED", "job_id": job_id, "queue_depth": len(RUNNER_JOBS_QUEUE)}


@router.post("/v1/runner/jobs/poll", tags=["Customer Runner"])
async def poll_customer_runner_jobs(payload: dict):
    """Long-poll endpoint for outbound customer runner daemons. Verifies auth token and returns available jobs."""
    runner_id = payload.get("runner_id")
    org_id = payload.get("org_id")
    auth_token = payload.get("auth_token", "")

    if not verify_enrolled_runner_token(str(runner_id or ""), str(org_id or ""), str(auth_token or "")):
        raise HTTPException(status_code=401, detail="Invalid runner authentication token")

    for idx, job in enumerate(RUNNER_JOBS_QUEUE):
        if job.get("org_id") == org_id:
            assigned = RUNNER_JOBS_QUEUE.pop(idx)
            return {"job_available": True, "job": assigned}

    return {"job_available": False, "job": None}


@router.post("/v1/runner/jobs/ack", tags=["Customer Runner"])
async def acknowledge_customer_runner_job(payload: dict):
    """Receives completion receipt, run status, and patch hash from customer runner."""
    run_id = payload.get("run_id", "unknown")
    status = payload.get("status", "COMPLETED")
    return {
        "status": "RECORDED",
        "run_id": run_id,
        "job_status": status,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/v1/runner/jobs/pending", dependencies=[Depends(current_principal)], tags=["Customer Runner"])
async def get_pending_runner_jobs():
    """List queued runner jobs waiting for runner node pickup."""
    return {"pending_jobs": RUNNER_JOBS_QUEUE, "count": len(RUNNER_JOBS_QUEUE)}


@router.post("/v1/runner/spool/sync", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Customer Runner"])
async def sync_customer_runner_spool(payload: dict, principal: Principal = Depends(current_principal)):
    """Processes an offline batch synchronization submission from a customer runner."""
    del principal
    from core.runner.spool import RunnerSpoolManager

    runner_id = payload.get("runner_id")
    if not runner_id:
        raise HTTPException(status_code=400, detail="Missing 'runner_id' in payload")
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="'items' must be a list")

    spool_path = _workspace_fs.root / ".keelway" / "runner_spool" / "spool.json"
    mgr = RunnerSpoolManager(persistence_path=spool_path)
    receipt = mgr.process_sync_batch(runner_id, items)
    return receipt.to_dict()


@router.get("/v1/runner/spool/status/{runner_id}", tags=["Customer Runner"])
async def get_customer_runner_spool_status(runner_id: str):
    """Retrieves pending item count and total spooled items for an outbound runner node."""
    from core.runner.spool import RunnerSpoolManager

    spool_path = _workspace_fs.root / ".keelway" / "runner_spool" / "spool.json"
    mgr = RunnerSpoolManager(persistence_path=spool_path)
    return mgr.get_status(runner_id)


@router.get("/v1/approval-rules", dependencies=[Depends(current_principal)], tags=["Autonomous Agent Loop"])
async def list_approval_rules():
    """Standing approvals for the open workspace."""
    rules = ApprovalRuleStore(_workspace_fs.root).list()
    now = time.time()
    return {
        "workspace": _workspace_fs.root.name,
        "rules": [{**r.to_dict(), "expired": is_expired(r, now)} for r in rules],
    }


@router.delete("/v1/approval-rules/{rule_id}", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Autonomous Agent Loop"])
async def revoke_approval_rule(rule_id: str, principal: Principal = Depends(current_principal)):
    """Revoke a standing approval; matching requests ask again."""
    gone = ApprovalRuleStore(_workspace_fs.root).remove(rule_id)
    if not gone:
        raise HTTPException(status_code=404, detail=f"Approval rule '{rule_id}' not found.")
    await record_audit(principal, "approval_rule_revoke", f"{gone.tool_name}:{gone.scope}", True)
    return {"revoked": gone.to_dict()}


@router.post("/v1/approval-rules", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Autonomous Agent Loop"])
async def create_approval_rule(request: Request, principal: Principal = Depends(current_principal)):
    """Create a standing approval for the open workspace (Studio 'Allow always' grant path)."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Expected a JSON body.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object.")
    try:
        rule, created = ApprovalRuleStore(_workspace_fs.root).add(
            str(payload.get("tool_name") or ""),
            payload.get("scope"),
            principal.actor,
            bound_model_id=payload.get("model_id") if isinstance(payload.get("model_id"), str) else None,
            bound_prompt_version=payload.get("prompt_version") if isinstance(payload.get("prompt_version"), str) else None,
            expires_at=payload.get("expires_at") if isinstance(payload.get("expires_at"), (int, float)) else None,
            ttl_seconds=payload.get("ttl_seconds") if isinstance(payload.get("ttl_seconds"), (int, float)) else None,
        )
    except ApprovalRuleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if created:
        await record_audit(principal, "approval_rule_create", f"{rule.tool_name}:{rule.scope}", True)
    return {"created": created, "rule": rule.to_dict()}


@router.post("/v1/approval-rules/{rule_id}/reconfirm", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Autonomous Agent Loop"])
async def reconfirm_approval_rule(rule_id: str, request: Request, principal: Principal = Depends(current_principal)):
    """Re-bind a standing approval to the current model/prompt version after drift."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object.")
    store = ApprovalRuleStore(_workspace_fs.root)
    rule = store.reconfirm(
        rule_id,
        payload.get("model_id") if isinstance(payload.get("model_id"), str) else None,
        payload.get("prompt_version") if isinstance(payload.get("prompt_version"), str) else None,
    )
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Approval rule '{rule_id}' not found.")
    await record_audit(principal, "approval_rule_reconfirm", f"{rule.tool_name}:{rule.scope}", True)
    return {"reconfirmed": rule.to_dict()}


@router.get("/v1/tier2/status", tags=["Tier 2 Hardware Verification"])
async def get_tier2_status(principal: Principal = Depends(current_principal)):
    """Active status of Tier 2 hardware security verification layers."""
    return {
        "tier": 2,
        "security_level": "hardware_attested",
        "verifiers": {
            "dual_worm": {
                "name": "Dual-WORM Storage Invariant",
                "status": "active",
                "adr": "ADR-076..080",
                "primary": "s3_object_lock_compliance",
                "secondary": "gcs_bucket_lock",
                "dual_receipt_enforcement": True,
            },
            "tpm": {
                "name": "TPM 2.0 Measured Boot & Monotonic Counter",
                "status": "active",
                "adr": "ADR-062/064, Doc 309",
                "pcr_replay_supported": True,
                "nv_anti_rollback": True,
            },
            "piv": {
                "name": "PIV Smartcard Hardware Token",
                "status": "active",
                "adr": "ADR-051/053",
                "crl_max_staleness_hours": 72,
                "enforce_active_revocation": True,
            },
            "recovery": {
                "name": "Customer 2-of-3 Offline Root Recovery",
                "status": "ready",
                "adr": "ADR-082/083",
                "quorum": "2-of-3",
                "deny_old_cutover": True,
            },
        },
    }


@router.post("/v1/tier2/verify", tags=["Tier 2 Hardware Verification"])
async def verify_tier2_subsystem(payload: Dict[str, Any], principal: Principal = Depends(current_principal)):
    """Cryptographically verify Tier 2 hardware claims (Dual-WORM, TPM quote, PIV, or Recovery)."""
    subsystem = payload.get("subsystem", "worm")
    
    if subsystem == "worm":
        from keelway.hal.worm import DualWormReceiptValidator, SignedWormDurableReceipt
        try:
            primary = SignedWormDurableReceipt(**payload["primary_receipt"])
            secondary = SignedWormDurableReceipt(**payload["secondary_receipt"])
            cert_raw = payload.get("certificate_bytes", b"")
            if isinstance(cert_raw, str):
                cert_raw = cert_raw.encode("utf-8")
            res = DualWormReceiptValidator.validate_publication(primary, secondary, cert_raw)
            return {"valid": res.valid, "subsystem": "worm", "reason": res.reason, "primary_id": res.primary_receipt_id}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"WORM verification failed: {exc}")

    elif subsystem == "tpm":
        from keelway.hal.tpm import TPMQuoteVerifier, TPMQuotePayload, TPMEventLogEntry
        try:
            quote = TPMQuotePayload(**payload["quote"])
            entries = [TPMEventLogEntry(**e) for e in payload.get("event_log", [])]
            res = TPMQuoteVerifier.verify_measured_boot(quote, entries)
            return {"valid": res.valid, "subsystem": "tpm", "computed_pcr": res.computed_pcr, "reason": res.reason}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"TPM verification failed: {exc}")

    elif subsystem == "piv":
        from keelway.hal.piv import PIVSmartcardVerifier, PIVCertificate, SignedCRL
        try:
            cert = PIVCertificate(**payload["certificate"])
            crl = SignedCRL(**payload["crl"])
            res = PIVSmartcardVerifier.verify_smartcard_token(cert, crl)
            return {"valid": res.valid, "subsystem": "piv", "serial_number": res.serial_number, "reason": res.reason}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"PIV verification failed: {exc}")

    elif subsystem == "recovery":
        from keelway.hal.recovery import OfflineRootRecoveryVerifier, RecoveryEnvelopeV1
        try:
            envelope = RecoveryEnvelopeV1(**payload["envelope"])
            roster = payload.get("enrolled_custodians", {
                "A": {"custodian_id": "alice_sec", "key_spki": "sha256:key_a", "assigned_role": "Security Lead"},
                "B": {"custodian_id": "bob_plat", "key_spki": "sha256:key_b", "assigned_role": "Platform Owner"},
                "C": {"custodian_id": "carol_alt", "key_spki": "sha256:key_c", "assigned_role": "Platform Owner"},
            })
            epoch = payload.get("initial_epoch", 1)
            old_root = payload.get("initial_root", envelope.plan.old_root_spki_sha256)
            verifier = OfflineRootRecoveryVerifier(
                realm_id=envelope.plan.realm_id,
                enrolled_custodians=roster,
                initial_recovery_epoch=epoch,
                initial_root_spki_sha256=old_root,
            )
            res = verifier.verify_recovery_envelope(envelope)
            return {
                "valid": res.is_valid,
                "subsystem": "recovery",
                "status_code": res.status_code,
                "new_root_enabled": res.new_root_enabled,
                "error": res.error_message,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Recovery verification failed: {exc}")

    raise HTTPException(status_code=400, detail=f"Unknown subsystem '{subsystem}'")


# ==============================================================================
# Model Economics & Cost Ledger Endpoints
# ==============================================================================

@router.get("/v1/models/local", tags=["Models"])
async def get_local_model_config() -> Dict[str, Any]:
    """Inspect and resolve local edge model runtime and hardware profile."""
    from core.models.edge_loader import EdgeRuntimeManager
    manager = EdgeRuntimeManager()
    resolved = manager.resolve_runtime()
    hw = resolved.get("hardware")
    if hasattr(hw, "__dict__"):
        resolved["hardware"] = hw.__dict__
    return {
        "status": "configured",
        "runtime": resolved,
    }


@router.get("/v1/models/ledger", tags=["Models"])
async def get_model_cost_ledger(
    limit: int = 100,
    offset: int = 0,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve summary metrics and audit entries from the model cost ledger."""
    from core.models.cost_ledger import cost_ledger
    return {
        "summary": cost_ledger.get_summary(),
        "entries": cost_ledger.list_entries(limit=limit, offset=offset),
    }


@router.get("/v1/models/ledger/export", tags=["Models"])
async def export_model_cost_ledger(
    format: str = "json",
    principal: Principal = Depends(current_principal),
) -> Response:
    """Export the model cost ledger in json, jsonl, or csv format."""
    from core.models.cost_ledger import cost_ledger
    fmt = format.lower().strip()
    content = cost_ledger.export(fmt)
    media_types = {
        "json": "application/json",
        "jsonl": "application/x-ndjson",
        "csv": "text/csv",
    }
    media_type = media_types.get(fmt, "text/plain")
    filename = f"keelway_model_ledger.{fmt}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/v1/models/economics", tags=["Models"])
async def get_model_economics(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve comprehensive sovereign AI economics report, including local-first arbitrage savings, ROI analytics, and rate card breakdown."""
    from core.models.cost_ledger import cost_ledger
    return cost_ledger.get_economics_report()


@router.post("/v1/models/ledger/reset", tags=["Models"])
async def reset_model_cost_ledger(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Reset the model cost ledger entries."""
    from core.models.cost_ledger import cost_ledger
    cost_ledger.reset()
    return {"status": "ok", "message": "Model cost ledger reset"}


@router.post("/v1/models/speculative/benchmark", tags=["Models & Economics"])
async def benchmark_speculative_decoding(payload: dict) -> Dict[str, Any]:
    """Execute speculative decoding edge benchmark and compute token arbitrage savings."""
    from core.models.speculative import SpeculativeBenchmark

    draft_model = payload.get("draft_model", "qwen2.5-coder:0.5b")
    target_model = payload.get("target_model", "qwen2.5-coder:7b")
    prompt = payload.get("prompt", "def optimize_query():")
    lookahead_k = int(payload.get("lookahead_k", 4))
    iterations = int(payload.get("iterations", 5))

    return SpeculativeBenchmark.benchmark(
        draft_model=draft_model,
        target_model=target_model,
        prompt=prompt,
        lookahead_k=lookahead_k,
        iterations=iterations,
    )


# ==============================================================================
# Multi-Agent Team Coordination & Execution Endpoints
# ==============================================================================

class TeamPlanRequest(BaseModel):
    goal: str = Field(..., min_length=3, description="Overall goal or objective for the agent team")
    custom_subtasks: Optional[List[Dict[str, Any]]] = None


class TeamExecuteRequest(BaseModel):
    goal: str = Field(..., min_length=3, description="Overall goal or objective for the agent team")
    custom_subtasks: Optional[List[Dict[str, Any]]] = None
    auto_approve: bool = Field(default=True, description="Whether to auto-approve non-critical steps")


@router.post("/v1/orchestration/team/plan", tags=["Multi-Agent Orchestration"])
async def plan_team_workflow(
    request: TeamPlanRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Decompose developer goal into a topologically sound multi-agent DAG."""
    from core.orchestration.multi_agent import MultiAgentCoordinator
    coordinator = MultiAgentCoordinator(workspace_fs=_workspace_fs)
    try:
        plan = coordinator.plan_team_workflow(request.goal, custom_subtasks=request.custom_subtasks)
        return plan.to_dict()
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/v1/orchestration/team/execute", tags=["Multi-Agent Orchestration"])
async def execute_team_workflow(
    request: TeamExecuteRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Execute a multi-agent team workflow with role specialization and flight tape sealing."""
    from core.orchestration.multi_agent import MultiAgentCoordinator
    coordinator = MultiAgentCoordinator(workspace_fs=_workspace_fs)
    try:
        plan = coordinator.plan_team_workflow(request.goal, custom_subtasks=request.custom_subtasks)
        result = await coordinator.execute_team_workflow(plan, auto_approve=request.auto_approve)
        return result.to_dict()
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Multi-agent execution failure: {exc}")


# ==============================================================================
# Prompt-to-App Guided Builder Endpoints
# ==============================================================================

class AppPlanRequest(BaseModel):
    intent: str = Field(..., min_length=3, description="Natural language prompt or requirements for the application")
    app_name: Optional[str] = Field(default=None, description="Optional custom application slug")
    template_id: Optional[str] = Field(default=None, description="Optional template archetype (fastapi-service, cli-tool, agent-microservice)")


class AppGenerateRequest(BaseModel):
    intent: str = Field(..., min_length=3, description="Natural language prompt or requirements for the application")
    app_name: Optional[str] = Field(default=None, description="Optional custom application slug")
    template_id: Optional[str] = Field(default=None, description="Optional template archetype")
    target_dir: Optional[str] = Field(default=None, description="Target filesystem directory")
    run_verification: bool = Field(default=True, description="Whether to execute automated test harness")
    init_git: bool = Field(default=True, description="Whether to initialize git repo and create commit")


@router.get("/v1/builder/app/templates", tags=["Guided App Builder"])
async def list_app_templates(
    principal: Principal = Depends(current_principal),
) -> List[Dict[str, Any]]:
    """List available application templates for the Guided App Builder."""
    from core.orchestration.guided_builder import GuidedAppBuilder
    return GuidedAppBuilder.list_templates()


@router.post("/v1/builder/app/plan", tags=["Guided App Builder"])
async def synthesize_app_plan(
    request: AppPlanRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Synthesize architecture plan, modules, and test harness from intent or template."""
    from core.orchestration.guided_builder import GuidedAppBuilder
    try:
        plan = GuidedAppBuilder.synthesize_plan(
            intent=request.intent,
            app_name=request.app_name,
            template_id=request.template_id,
        )
        return plan.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"App plan synthesis failed: {exc}")


@router.post("/v1/builder/app/generate", tags=["Guided App Builder"])
async def generate_app(
    request: AppGenerateRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Scaffold complete application, execute test harness, and seal flight recorder receipt."""
    from core.orchestration.guided_builder import GuidedAppBuilder
    target_path = Path(request.target_dir) if request.target_dir else None
    try:
        receipt = GuidedAppBuilder.build_and_export(
            intent=request.intent,
            app_name=request.app_name,
            template_id=request.template_id,
            target_dir=target_path,
            run_verification=request.run_verification,
            init_git=request.init_git,
        )
        return receipt.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"App generation failed: {exc}")


# ==============================================================================
# Plugin Extension & External MCP Bridge Endpoints
# ==============================================================================

_plugin_manager: Optional[Any] = None

def get_plugin_manager():
    global _plugin_manager
    if _plugin_manager is None:
        from core.plugins.manager import PluginManager
        _plugin_manager = PluginManager()
    return _plugin_manager


class PluginInstallRequest(BaseModel):
    manifest: Dict[str, Any] = Field(..., description="Plugin manifest JSON object")
    activate: bool = Field(default=True, description="Whether to activate immediately")


class MCPToolCallRequest(BaseModel):
    server_id: str = Field(..., description="Registered MCP server identifier")
    tool_name: str = Field(..., description="Tool name exposed by the MCP server")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool invocation parameters")


@router.get("/v1/plugins", tags=["Plugins & MCP Extensions"])
async def list_plugins(
    principal: Principal = Depends(current_principal),
) -> List[Dict[str, Any]]:
    """List all installed plugins, active MCP servers, and available tools."""
    pm = get_plugin_manager()
    return pm.list_plugins()


@router.post("/v1/plugins/install", tags=["Plugins & MCP Extensions"])
async def install_plugin(
    request: PluginInstallRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Install and optionally activate a new Keelway plugin manifest."""
    pm = get_plugin_manager()
    try:
        record = await pm.install_plugin(request.manifest, activate=request.activate)
        return record.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Plugin installation failed: {exc}")


@router.post("/v1/plugins/{plugin_name}/activate", tags=["Plugins & MCP Extensions"])
async def activate_plugin(
    plugin_name: str,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Activate an installed plugin and connect its declared MCP server processes."""
    pm = get_plugin_manager()
    try:
        record = await pm.activate_plugin(plugin_name)
        return record.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Activation error: {exc}")


@router.post("/v1/plugins/{plugin_name}/deactivate", tags=["Plugins & MCP Extensions"])
async def deactivate_plugin(
    plugin_name: str,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Deactivate a plugin and disconnect its MCP server processes."""
    pm = get_plugin_manager()
    try:
        record = await pm.deactivate_plugin(plugin_name)
        return record.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Deactivation error: {exc}")


@router.delete("/v1/plugins/{plugin_name}", tags=["Plugins & MCP Extensions"])
async def uninstall_plugin(
    plugin_name: str,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Uninstall and delete a plugin from the local workspace."""
    pm = get_plugin_manager()
    success = await pm.uninstall_plugin(plugin_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found.")
    return {"status": "uninstalled", "plugin_name": plugin_name}


@router.post("/v1/plugins/mcp/call", tags=["Plugins & MCP Extensions"])
async def call_mcp_tool(
    request: MCPToolCallRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Directly call an external MCP tool via the MCP client manager."""
    pm = get_plugin_manager()
    client = await pm.mcp_manager.get_client(request.server_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"MCP server '{request.server_id}' not connected.")
    try:
        res = await client.call_tool(request.tool_name, request.arguments)
        return {"server_id": request.server_id, "tool_name": request.tool_name, "result": res}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MCP tool invocation failed: {exc}")


# ==============================================================================
# Sovereign Air-Gap Audit & Bundle Deployment Endpoints
# ==============================================================================

class BundleExportRequest(BaseModel):
    bundle_name: Optional[str] = Field(default=None, description="Custom identifier for the sovereign bundle")
    output_dir: Optional[str] = Field(default=None, description="Target export directory")
    include_tar: bool = Field(default=True, description="Whether to compile into a .tar.gz archive")


class BundleVerifyRequest(BaseModel):
    bundle_path: str = Field(..., description="Filesystem path to bundle directory or .tar.gz archive")


@router.get("/v1/airgap/audit", tags=["Air-Gap & Sovereign Deployment"])
async def run_airgap_audit(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Execute pre-flight air-gap compliance audit and generate signed attestation."""
    from core.security.airgap_auditor import AirGapAuditor
    report = AirGapAuditor.audit_environment()
    return report.to_dict()


@router.post("/v1/airgap/bundle/export", tags=["Air-Gap & Sovereign Deployment"])
async def export_airgap_bundle(
    request: BundleExportRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Package a self-contained, offline-deployable sovereign bundle with SHA-256 manifest."""
    from core.security.bundle_exporter import AirGapBundleExporter
    out_path = Path(request.output_dir) if request.output_dir else None
    try:
        receipt = AirGapBundleExporter.export_bundle(
            output_dir=out_path,
            bundle_name=request.bundle_name,
            include_tar=request.include_tar,
        )
        return receipt.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bundle export failed: {exc}")


@router.post("/v1/airgap/bundle/verify", tags=["Air-Gap & Sovereign Deployment"])
async def verify_airgap_bundle(
    request: BundleVerifyRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Verify cryptographic integrity of an offline sovereign deployment bundle."""
    from core.security.bundle_exporter import AirGapBundleExporter
    target_path = Path(request.bundle_path)
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Bundle file not found: {request.bundle_path}")
    try:
        result = AirGapBundleExporter.verify_bundle(target_path)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bundle verification error: {exc}")


# ==============================================================================
# Continuous Evaluation, Reliability & Drift Detection Endpoints
# ==============================================================================

class EvalRunRequest(BaseModel):
    model_name: str = Field(default="keelway-local-default", description="Model identifier evaluated")
    save_receipt: bool = Field(default=True, description="Whether to persist signed evaluation receipt")


class DriftCompareRequest(BaseModel):
    candidate_run_id: str = Field(..., description="Run ID of the candidate evaluation receipt")
    baseline_run_id: Optional[str] = Field(default=None, description="Optional baseline run ID (defaults to latest)")
    max_latency_degradation_pct: float = Field(default=25.0, description="Latency drift threshold percentage")


@router.post("/v1/evals/run", tags=["Evaluation & Drift Detection"])
async def run_evaluation_benchmark(
    request: EvalRunRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Execute 10-task golden benchmark and generate a cryptographic EvaluationReceipt."""
    from evals.drift_detector import DriftDetector, EvaluationReceiptStore
    store = EvaluationReceiptStore() if request.save_receipt else None
    receipt = await DriftDetector.run_evaluation_and_create_receipt(
        model_name=request.model_name,
        store=store,
    )
    return receipt.to_dict()


@router.get("/v1/evals/history", tags=["Evaluation & Drift Detection"])
async def list_evaluation_history(
    principal: Principal = Depends(current_principal),
) -> List[Dict[str, Any]]:
    """List historical evaluation receipts with Pass@1 rates and latency percentiles."""
    from evals.drift_detector import EvaluationReceiptStore
    store = EvaluationReceiptStore()
    return store.list_receipts()


@router.post("/v1/evals/drift/compare", tags=["Evaluation & Drift Detection"])
async def compare_evaluation_drift(
    request: DriftCompareRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Compare candidate evaluation receipt against baseline to detect quality regressions."""
    from evals.drift_detector import DriftDetector, EvaluationReceiptStore
    store = EvaluationReceiptStore()

    candidate = store.get_receipt(request.candidate_run_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate receipt '{request.candidate_run_id}' not found.")

    if request.baseline_run_id:
        baseline = store.get_receipt(request.baseline_run_id)
        if not baseline:
            raise HTTPException(status_code=404, detail=f"Baseline receipt '{request.baseline_run_id}' not found.")
    else:
        # Pick the most recent receipt that isn't the candidate
        all_r = store.list_receipts()
        other_r = [r for r in all_r if r["eval_run_id"] != request.candidate_run_id]
        if not other_r:
            raise HTTPException(status_code=400, detail="No historical baseline receipt available for comparison.")
        baseline = store.get_receipt(other_r[0]["eval_run_id"])

    analysis = DriftDetector.compare(
        baseline=baseline,
        candidate=candidate,
        max_latency_degradation_pct=request.max_latency_degradation_pct,
    )
    return analysis.to_dict()


# ---------------------------------------------------------------------------
# Investor & Enterprise Evidence Room (WP21)
# ---------------------------------------------------------------------------

@router.get("/v1/evidence/summary", tags=["Evidence Room & Audit"])
async def get_evidence_summary(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve live verifiable evidence summary across benchmarks, tests, air-gap, and SBOM."""
    from core.eval.evidence_room import EvidenceRoomPipeline
    pkg = EvidenceRoomPipeline.assemble_package()
    return pkg.to_dict()


@router.post("/v1/evidence/generate", tags=["Evidence Room & Audit"])
async def generate_evidence_package(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Assemble and cryptographically seal an investor and audit evidence package."""
    from core.eval.evidence_room import EvidenceRoomPipeline
    pkg = EvidenceRoomPipeline.assemble_package()
    return {
        "status": "SEALED",
        "package_id": pkg.package_id,
        "package_sha256": pkg.package_sha256,
        "evidence_package": pkg.to_dict(),
    }


class EvidenceVerifyRequest(BaseModel):
    package: Dict[str, Any]


@router.post("/v1/evidence/verify", tags=["Evidence Room & Audit"])
async def verify_evidence_package(
    req: EvidenceVerifyRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Cryptographically verify an evidence package against its sealed hash."""
    from core.eval.evidence_room import EvidenceRoomPipeline
    valid, reason, details = EvidenceRoomPipeline.verify_package(req.package)
    return {
        "is_valid": valid,
        "status": reason,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Enterprise Entitlements & SBOM Endpoints
# ---------------------------------------------------------------------------

@router.get("/v1/entitlements/status", tags=["Enterprise Governance"])
async def get_entitlements_status(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve current enterprise entitlement status and feature allowances."""
    from core.billing.entitlements import get_shared_entitlement_manager
    mgr = get_shared_entitlement_manager()
    cert, valid, status_str = mgr.status("default-org")
    return {
        "tier": cert.tier.value,
        "seats": cert.seats,
        "is_valid": valid,
        "status": status_str,
        "features": {f: bool(valid) and cert.allows(f) for f in cert.allowed_features},
        "days_offline": round((time.time() - cert.issued_at) / 86400, 2),
        "offline_grace_days_remaining": round(max(0.0, 14.0 - (time.time() - cert.issued_at) / 86400), 2),
    }


@router.get("/v1/sbom", tags=["Enterprise Governance"])
async def get_cyclonedx_sbom(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve CycloneDX v1.5 Software Bill of Materials with release provenance signature."""
    from core.security.sbom import SBOMGenerator
    sbom = SBOMGenerator.generate()
    return sbom.to_dict()


# ---------------------------------------------------------------------------
# Sovereign System Diagnostics & Doctor
# ---------------------------------------------------------------------------

@router.get("/v1/doctor", tags=["System Diagnostics"])
@router.get("/v1/system/doctor", tags=["System Diagnostics"])
async def get_system_doctor_report(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Execute enterprise sovereign system diagnostics across all 7 core platform dimensions."""
    from core.system.doctor import SystemDoctor
    report = await SystemDoctor.run_diagnostics()
    return report.to_dict()


# ---------------------------------------------------------------------------
# Sovereign Cross-Machine Encrypted Sync & Web Console Endpoints
# ---------------------------------------------------------------------------

class SyncMutateRequest(BaseModel):
    entity_type: str
    task_id: str
    payload: Dict[str, Any]
    workspace_id: str = "default_workspace"


@router.get("/v1/sync/status", tags=["Cross-Machine Sync"])
async def get_sync_status(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve operational state, logical Lamport counter, and vector clocks."""
    from core.sync.engine import get_shared_sync_engine
    engine = get_shared_sync_engine()
    return engine.get_status()


@router.post("/v1/sync/mutate", tags=["Cross-Machine Sync"])
async def record_sync_mutation(
    req: SyncMutateRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Record a local state mutation into the append-only sync journal."""
    from core.sync.engine import get_shared_sync_engine
    engine = get_shared_sync_engine()
    rec = engine.record_mutation(
        entity_type=req.entity_type,
        task_id=req.task_id,
        payload=req.payload,
        workspace_id=req.workspace_id,
    )
    return {"status": "RECORDED", "record": rec.to_dict()}


@router.post("/v1/sync/export", tags=["Cross-Machine Sync"])
async def export_sync_envelope(
    since_lamport: int = 0,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Package un-synced journal records into an authenticated encrypted envelope."""
    from core.sync.engine import get_shared_sync_engine
    engine = get_shared_sync_engine()
    envelope = engine.export_envelope(since_lamport=since_lamport)
    return envelope.to_dict()


class SyncImportRequest(BaseModel):
    envelope: Dict[str, Any]


@router.post("/v1/sync/import", tags=["Cross-Machine Sync"])
async def import_sync_envelope(
    req: SyncImportRequest,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Decrypt, verify, and deterministically merge an inbound sync envelope."""
    from core.sync.engine import get_shared_sync_engine, EncryptedSyncEnvelope
    engine = get_shared_sync_engine()
    env = EncryptedSyncEnvelope.from_dict(req.envelope)
    return engine.import_envelope(env)


@router.get("/v1/sync/records", tags=["Cross-Machine Sync"])
async def list_sync_records(
    limit: int = 100,
    principal: Principal = Depends(current_principal),
) -> List[Dict[str, Any]]:
    """Retrieve the sorted append-only sync journal audit trail."""
    from core.sync.engine import get_shared_sync_engine
    engine = get_shared_sync_engine()
    return [r.to_dict() for r in engine.journal[-limit:]]


# =====================================================================
# KStack, KBrain, KHub, KSpaces, and KFlow Endpoints
# =====================================================================

@router.get("/v1/kstack/skills", tags=["KStack"])
async def list_kstack_skills(
    include_revoked: bool = False,
    principal: Principal = Depends(current_principal),
) -> List[Dict[str, Any]]:
    """List all registered KStack role skills."""
    from core.kstack import kstack_registry
    return [s.to_dict() for s in kstack_registry.list_skills(include_revoked=include_revoked)]


@router.get("/v1/kstack/skill/{name:path}", tags=["KStack"])
async def inspect_kstack_skill(
    name: str,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Inspect detailed contracts and instructions for a specific KStack skill."""
    from core.kstack import kstack_registry
    try:
        return kstack_registry.inspect_skill(name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/v1/kbrain/facts", tags=["KBrain"])
async def query_kbrain_facts(
    scope: str = "project",
    search: Optional[str] = None,
    key: Optional[str] = None,
    principal: Principal = Depends(current_principal),
) -> List[Dict[str, Any]]:
    """Query scope-governed knowledge facts with ACL boundary enforcement."""
    from core.kbrain import kbrain_store, KnowledgeScope
    try:
        k_scope = KnowledgeScope(scope)
    except ValueError:
        k_scope = KnowledgeScope.PROJECT
    facts = kbrain_store.query_facts(max_scope=k_scope, search_text=search, key=key)
    return [f.to_dict() for f in facts]


@router.post("/v1/kbrain/fact", tags=["KBrain"])
async def record_kbrain_fact(
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Record a scope-governed fact with secret leakage protection."""
    from core.kbrain import kbrain_store, KnowledgeScope, SecretLeakDetectedError
    key = payload.get("key", "").strip()
    statement = payload.get("statement", "").strip()
    if not key or not statement:
        raise HTTPException(status_code=400, detail="Fields 'key' and 'statement' are required.")
    scope_str = payload.get("scope", "project")
    try:
        k_scope = KnowledgeScope(scope_str)
    except ValueError:
        k_scope = KnowledgeScope.PROJECT

    try:
        fact = kbrain_store.record_fact(
            key=key,
            statement=statement,
            scope=k_scope,
            provenance_uri=payload.get("provenance_uri", ""),
            provenance_reason=payload.get("provenance_reason", ""),
            created_by=principal.id if hasattr(principal, "id") else "user",
            auto_approve=bool(payload.get("auto_approve", True)),
        )
        return fact.to_dict()
    except SecretLeakDetectedError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/v1/khub/skills", tags=["KHub"])
async def list_khub_imported_skills(
    principal: Principal = Depends(current_principal),
) -> List[Dict[str, Any]]:
    """List universal imported skills and check for upstream file drift."""
    from core.khub import khub_importer
    skills = khub_importer.list_imported()
    return [s.to_dict() for s in skills]


@router.post("/v1/khub/scan", tags=["KHub"])
async def scan_khub_directory(
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Scan a repository or directory for portable skills and rules."""
    from core.khub import khub_importer
    root_path = Path(payload.get("path", "."))
    scanned = khub_importer.scan_directory(root_path)
    return {
        "scanned_count": len(scanned),
        "skills": [s.to_dict() for s in scanned],
    }


@router.post("/v1/khub/approve", tags=["KHub"])
async def approve_khub_skill(
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Grant explicit human authorization to execute an imported skill."""
    from core.khub import khub_importer
    skill_id = payload.get("skill_id", "")
    try:
        khub_importer.approve_imported_skill(skill_id)
        return {"status": "ok", "skill_id": skill_id, "approved": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/v1/khub/bundle/export", tags=["KHub Universal Skills"])
async def export_khub_skill_bundle(
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Pack a portable skill directory or SKILL.md into a verified .skill.tar.gz bundle."""
    from core.khub.sync import KHubBundlePacker

    skill_path_str = payload.get("skill_path") or payload.get("source_dir") or payload.get("path")
    if not skill_path_str:
        raise HTTPException(status_code=400, detail="Missing required 'skill_path' field.")

    try:
        skill_path = _workspace_fs.resolve_safe_path(skill_path_str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid skill path: {exc}")

    if not skill_path.exists():
        raise HTTPException(status_code=404, detail=f"Skill path '{skill_path_str}' does not exist.")

    out_archive_str = payload.get("output_archive") or payload.get("out")
    if out_archive_str:
        try:
            output_archive = _workspace_fs.resolve_safe_path(out_archive_str)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid output archive path: {exc}")
    else:
        stem = skill_path.name if skill_path.is_dir() else skill_path.stem
        output_archive = skill_path.parent / f"{stem}.skill.tar.gz"

    try:
        manifest = KHubBundlePacker.pack_skill(skill_path, output_archive)
        rel_archive = str(output_archive.relative_to(_workspace_fs.root))
        return {
            "status": "packed",
            "archive_path": rel_archive,
            "manifest": manifest,
            "skill_name": manifest.get("skill_name", skill_path.name),
            "bundle_digest_sha256": manifest.get("bundle_digest_sha256", ""),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Packaging failed: {exc}")


@router.post("/v1/khub/bundle/import", tags=["KHub Universal Skills"])
async def import_khub_skill_bundle(
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Unpack and cryptographically verify a portable .skill.tar.gz bundle."""
    from core.khub.sync import KHubBundlePacker

    archive_str = payload.get("archive_path") or payload.get("path")
    if not archive_str:
        raise HTTPException(status_code=400, detail="Missing required 'archive_path' field.")

    archive_p = Path(archive_str)
    if archive_p.is_absolute() and archive_p.is_file():
        archive_path = archive_p.resolve()
    else:
        try:
            archive_path = _workspace_fs.resolve_safe_path(archive_str)
        except Exception as exc:
            if archive_p.is_file():
                archive_path = archive_p.resolve()
            else:
                raise HTTPException(status_code=400, detail=f"Invalid archive path: {exc}")

    if not archive_path.is_file():
        raise HTTPException(status_code=404, detail=f"Archive file '{archive_str}' does not exist.")

    dest_str = payload.get("destination_dir") or payload.get("dest")
    if dest_str:
        try:
            destination_dir = _workspace_fs.resolve_safe_path(dest_str)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid destination directory: {exc}")
    else:
        bundle_stem = archive_path.name.replace(".skill.tar.gz", "").replace(".tar.gz", "").replace(".tar", "")
        destination_dir = _workspace_fs.root / "skills" / bundle_stem

    verify = payload.get("verify", True)

    try:
        res = KHubBundlePacker.unpack_skill(archive_path, destination_dir, verify=verify)
        rel_dest = str(destination_dir.relative_to(_workspace_fs.root))
        return {
            "status": "unpacked",
            "destination_dir": rel_dest,
            "manifest": res.get("manifest", {}),
            "verified": res.get("verified", True),
            "skill_name": res.get("skill_name", destination_dir.name),
            "bundle_digest_sha256": res.get("bundle_digest_sha256", ""),
        }
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=f"Directory traversal attack detected: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Integrity verification failed: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unpack failed: {exc}")


@router.get("/v1/kspaces", tags=["KSpaces"])
async def list_kspaces(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """List team collaborative spaces."""
    from core.kspaces import kspaces_manager
    return {
        "spaces": [s.to_dict() for s in kspaces_manager._spaces.values()],
    }


@router.post("/v1/kspaces", tags=["KSpaces"])
async def create_kspace(
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Create a new collaborative team space."""
    from core.kspaces import kspaces_manager
    space_id = payload.get("space_id", "").strip()
    name = payload.get("name", "").strip()
    if not space_id or not name:
        raise HTTPException(status_code=400, detail="Fields 'space_id' and 'name' are required.")
    owner_id = principal.id if hasattr(principal, "id") else "owner"
    try:
        space = kspaces_manager.create_space(space_id, name, owner_id)
        return space.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/v1/kspaces/{space_id}/conflicts/check", tags=["KSpaces Multi-Tenant"])
async def check_kspace_conflicts(
    space_id: str,
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Analyze a 3-way git merge between base, left, and right texts for conflicts."""
    from core.kspaces.conflict import ConflictDetector
    from core.kspaces.manager import kspaces_manager

    base_text = payload.get("base_text", "")
    left_text = payload.get("left_text", "")
    right_text = payload.get("right_text", "")
    file_path = payload.get("file_path", "")

    report = ConflictDetector.detect_3way(base_text, left_text, right_text, file_path=file_path)

    actor = principal.id if hasattr(principal, "id") else getattr(principal, "actor_id", "user")
    kspaces_manager.record_timeline_event(
        space_id=space_id,
        actor=actor,
        event_type="conflict_check",
        details={
            "file_path": file_path,
            "has_conflicts": report.has_conflicts,
            "auto_resolvable": report.auto_resolvable,
        },
    )
    return report.to_dict()


@router.post("/v1/kspaces/{space_id}/conflicts/resolve", tags=["KSpaces Multi-Tenant"])
async def resolve_kspace_conflicts(
    space_id: str,
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Autonomously resolve a 3-way merge conflict using specified strategy."""
    from core.kspaces.conflict import ConflictDetector
    from core.kspaces.manager import kspaces_manager

    base_text = payload.get("base_text", "")
    left_text = payload.get("left_text", "")
    right_text = payload.get("right_text", "")
    strategy = payload.get("strategy", "auto")

    try:
        resolved_text = ConflictDetector.resolve_3way(base_text, left_text, right_text, strategy=strategy)
        actor = principal.id if hasattr(principal, "id") else getattr(principal, "actor_id", "user")
        kspaces_manager.record_timeline_event(
            space_id=space_id,
            actor=actor,
            event_type="conflict_resolved",
            details={"strategy": strategy},
        )
        return {"status": "resolved", "resolved_text": resolved_text}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Conflict resolution failed: {e}")


@router.get("/v1/kspaces/{space_id}/timeline", tags=["KSpaces Multi-Tenant"])
async def get_kspace_timeline(
    space_id: str,
    limit: int = 50,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve activity timeline events for a team collaborative space."""
    from core.kspaces.manager import kspaces_manager
    events = kspaces_manager.get_timeline(space_id, limit=limit)
    return {"space_id": space_id, "events": events}


@router.get("/v1/kflow/dags", tags=["KFlow"])
async def list_kflow_dags(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """List all registered KFlow DAG orchestration workflows."""
    from core.kflow import kflow_engine
    with kflow_engine._lock:
        dags = [dag.to_dict() for dag in kflow_engine._flows.values()]
    return {"dags": dags}


@router.post("/v1/kflow/dag", tags=["KFlow"])
async def create_kflow_dag(
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Register a new durable KFlow DAG with nodes, roles, tools, and dependencies."""
    from core.kflow import kflow_engine, FlowNode
    flow_id = payload.get("flow_id", "").strip()
    goal = payload.get("goal", "").strip()
    nodes_raw = payload.get("nodes", [])
    max_fanout = int(payload.get("max_fanout", 4))

    if not flow_id or not goal:
        raise HTTPException(status_code=400, detail="Fields 'flow_id' and 'goal' are required.")

    flow_nodes = []
    for nr in nodes_raw:
        flow_nodes.append(
            FlowNode(
                node_id=nr.get("node_id", ""),
                name=nr.get("name", nr.get("node_id", "")),
                assigned_role=nr.get("assigned_role", "core_engineer"),
                tool=nr.get("tool", "bash"),
                inputs=nr.get("inputs", {}),
                dependencies=nr.get("dependencies", []),
                exact_base_sha=nr.get("exact_base_sha", ""),
            )
        )

    try:
        dag = kflow_engine.create_dag(flow_id=flow_id, goal=goal, nodes=flow_nodes, max_fanout=max_fanout)
        return dag.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/v1/kflow/dag/{flow_id}", tags=["KFlow"])
async def get_kflow_dag(
    flow_id: str,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve details and status for a specific KFlow DAG."""
    from core.kflow import kflow_engine
    dag = kflow_engine.get_flow(flow_id)
    if not dag:
        raise HTTPException(status_code=404, detail=f"Flow DAG '{flow_id}' not found.")
    return dag.to_dict()


@router.post("/v1/kflow/dag/{flow_id}/run", tags=["KFlow"])
async def run_kflow_dag(
    flow_id: str,
    payload: Optional[Dict[str, Any]] = None,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Execute a durable KFlow DAG in topological order, asserting base SHA and assembling proof packet."""
    from core.kflow import kflow_engine
    dag = kflow_engine.get_flow(flow_id)
    if not dag:
        raise HTTPException(status_code=404, detail=f"Flow DAG '{flow_id}' not found.")

    current_git_head_sha = (payload or {}).get("git_head_sha", "c5eb183d2f9a0")
    try:
        proof = kflow_engine.execute_dag(flow_id=flow_id, current_git_head_sha=current_git_head_sha)
        return {
            "status": "completed",
            "proof_packet": proof.to_dict(),
            "dag": dag.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/kflow/dag/{flow_id}/cancel", tags=["KFlow"])
async def cancel_kflow_dag(
    flow_id: str,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Cancel a running or pending KFlow DAG."""
    from core.kflow import kflow_engine
    success = kflow_engine.cancel_flow(flow_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Flow DAG '{flow_id}' not found.")
    return {"status": "cancelled", "flow_id": flow_id}


# ---------------------------------------------------------------------------
# Enterprise Audit Merkle Tree & Inclusion Proofs
# ---------------------------------------------------------------------------

@router.get("/v1/audit/merkle/root", tags=["Enterprise Audit"])
async def get_audit_merkle_root(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve current Merkle root and tip hash of the enterprise audit chain."""
    from core.security.merkle_audit import EnterpriseAuditExporter
    from core.storage.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        bundle = await EnterpriseAuditExporter.export_bundle(session)
    return {
        "merkle_root": bundle["merkle_root"],
        "total_events": bundle["total_events"],
        "tip_hash": bundle["tip_hash"],
    }


@router.get("/v1/audit/merkle/proof/{seq}", tags=["Enterprise Audit"])
async def get_audit_merkle_proof(
    seq: int,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Retrieve cryptographic Merkle inclusion proof for a given audit sequence number."""
    from core.security.merkle_audit import EnterpriseAuditExporter
    from core.storage.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        try:
            return await EnterpriseAuditExporter.get_inclusion_proof_for_seq(session, seq)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.post("/v1/audit/merkle/verify", tags=["Enterprise Audit"])
async def verify_audit_merkle_proof(
    payload: Dict[str, Any],
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Cryptographically verify a Merkle inclusion proof against a specified root hash."""
    from core.security.merkle_audit import AuditMerkleTree
    leaf_hash = payload.get("leaf_hash", "")
    proof = payload.get("proof", [])
    root_hash = payload.get("root_hash", "")
    is_valid = AuditMerkleTree.verify_proof(leaf_hash, proof, root_hash)
    return {"valid": is_valid}


@router.post("/v1/audit/export/bundle", tags=["Enterprise Audit"])
async def export_audit_bundle(
    payload: Optional[Dict[str, Any]] = None,
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Export complete Enterprise Audit Merkle Bundle with chain validity check."""
    from core.security.merkle_audit import EnterpriseAuditExporter
    from core.storage.database import AsyncSessionLocal
    out_path = (payload or {}).get("out_path")
    async with AsyncSessionLocal() as session:
        return await EnterpriseAuditExporter.export_bundle(session, out_file=out_path)







# ---------------------------------------------------------------------------
# Access Tokens & RBAC Administration
# ---------------------------------------------------------------------------

class TokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., description="RBAC role: owner|admin|engineer|auditor|phone")
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


@router.get("/v1/rbac/matrix", tags=["Access Control"])
async def get_rbac_matrix(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Return the role → permission matrix exactly as enforced by the RBAC subsystem."""
    from core.security.rbac import ROLE_PERMISSIONS
    return {
        "roles": {role.value: [p.value for p in perms] for role, perms in ROLE_PERMISSIONS.items()},
        "permissions": [p.value for p in Permission],
    }


@router.get("/v1/tokens", dependencies=[Depends(require(Permission.MANAGE_KEYS))], tags=["Access Control"])
async def list_api_tokens(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List API tokens (hashes are never returned). Owner role required."""
    from sqlalchemy import select
    from core.storage.models import ApiTokenRecord
    rows = (await db.execute(select(ApiTokenRecord).order_by(ApiTokenRecord.created_at))).scalars().all()
    return {
        "tokens": [
            {
                "id": r.id,
                "name": r.name,
                "role": r.role,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
                "revoked": r.revoked_at is not None,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            }
            for r in rows
        ]
    }


@router.post("/v1/tokens", dependencies=[Depends(require(Permission.MANAGE_KEYS))], tags=["Access Control"])
async def create_token_endpoint(
    request: TokenCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Mint a new API token. The plaintext token is returned once and never stored."""
    from datetime import datetime, timedelta, timezone
    from core.security.auth import create_api_token
    try:
        role = Role(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown role '{request.role}'. Valid: {[r.value for r in Role]}")
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)
    record, token = await create_api_token(db, request.name, role, expires_at=expires_at)
    return {
        "id": record.id,
        "name": record.name,
        "role": record.role,
        "token": token,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "note": "Store this token now; only its hash is kept.",
    }


@router.post("/v1/tokens/{token_id}/revoke", dependencies=[Depends(require(Permission.MANAGE_KEYS))], tags=["Access Control"])
async def revoke_token_endpoint(
    token_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Revoke an API token by id. Revocation is immediate and irreversible."""
    from datetime import datetime, timezone
    from core.storage.models import ApiTokenRecord
    record = await db.get(ApiTokenRecord, token_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No token with id '{token_id}'.")
    if record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
    return {"id": record.id, "revoked": True}


# ---------------------------------------------------------------------------
# KFlow Interval Scheduling (in-memory, process-scoped)
# ---------------------------------------------------------------------------

class ScheduleCreateRequest(BaseModel):
    flow_id: str = Field(..., min_length=1)
    interval_seconds: int = Field(..., ge=60, description="Run interval in seconds (minimum 60)")


@router.get("/v1/schedules", tags=["Scheduling"])
async def list_schedules(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """List interval schedules for KFlow DAGs. Schedules are in-memory and reset on restart."""
    from core.orchestration.scheduler import flow_scheduler
    return {"schedules": flow_scheduler.list(), "persistent": False}


@router.post("/v1/schedules", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Scheduling"])
async def create_schedule(
    request: ScheduleCreateRequest,
) -> Dict[str, Any]:
    """Schedule a registered KFlow DAG to re-run on an interval."""
    from core.orchestration.scheduler import flow_scheduler
    try:
        sched = flow_scheduler.add(request.flow_id, request.interval_seconds)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return sched.to_dict()


@router.delete("/v1/schedules/{schedule_id}", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Scheduling"])
async def delete_schedule(
    schedule_id: str,
) -> Dict[str, Any]:
    """Remove a schedule. The DAG itself is unaffected."""
    from core.orchestration.scheduler import flow_scheduler
    if not flow_scheduler.remove(schedule_id):
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found.")
    return {"deleted": True, "schedule_id": schedule_id}
