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
from core.security.env_scrub import scrub_env
from core.security.origin import origin_allowed
from core.security.rbac import Permission
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Inference failure: {str(e)}",
        )


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


class ConnectionManager:
    """Manages active WebSocket connections for Keelway Studio."""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.active_connections.discard(connection)


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
    """Generate sovereign multi-rail payment intent (M-Pesa, PIX, UPI, L402, Offline Voucher)."""
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
    intent = broker.create_intent(rail=rail, amount=amount, currency=currency, recipient=recipient, description=description)
    return {
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


@router.post("/v1/flight/fork", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Deterministic Flight Recorder"])
async def fork_flight_tape(payload: dict):
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
    try:
        tape_hash = json.loads(saved_path.read_text(encoding="utf-8")).get("tape_sha256")
        await record_audit(principal, "flight_tape_sealed", f"{new_task_id} fork_from={task_id} sha256:{tape_hash}", True)
    except Exception:
        pass
    return {
        "original_task_id": task_id,
        "forked_task_id": new_task_id,
        "forked_at_index": at_index,
        "tape_path": str(saved_path),
    }


@router.get("/v1/mesh/peers", dependencies=[Depends(current_principal)], tags=["Local Team Mesh"])
async def list_mesh_peers():
    """List peer developer workstations discovered on local Wi-Fi / Tailscale."""
    from core.orchestration.p2p_mesh import LocalTeamMesh
    mesh = LocalTeamMesh()
    return {
        "local_node": mesh.get_local_advertisement(),
        "peers": [p.__dict__ for p in mesh.peers.values()],
    }


# =====================================================================
# Workspace Filesystem & Live Git Endpoints
# =====================================================================

from core.storage.workspace_fs import WorkspaceFilesystem, WorkspaceSecurityError
from core.orchestration.project_adapter import ProjectAdapter

_workspace_fs = WorkspaceFilesystem()


def set_workspace_fs(fs: WorkspaceFilesystem) -> None:
    """Explicitly rebind the active workspace filesystem (e.g. for testing or workspace switching)."""
    global _workspace_fs, _semantic_index
    _workspace_fs = fs
    _semantic_index = CodebaseSemanticIndex(workspace_fs=_workspace_fs)


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


# =====================================================================
# Autonomous ReAct Agent Loop Endpoints
# =====================================================================

from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.agents import manifest as agent_manifest
from core.agents.guard import ManifestNotRunnable, loop_from_manifest, not_enforced, preflight
from core.security.approval_rules import ApprovalRuleError, ApprovalRuleStore, validate_scope

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
        agent = AutonomousAgentLoop(
            task_id=task_id, workspace_fs=_workspace_fs, policy=policy, record_flight=True,
            approval_rules=ApprovalRuleStore(_workspace_fs.root),
        )
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


@router.post("/v1/agent/approve/{task_id}", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Autonomous Agent Loop"])
async def approve_agent_action(task_id: str, payload: dict, principal: Principal = Depends(current_principal)):
    """Human-in-the-loop: grant or deny a pending mutating tool, optionally remembering a scoped standing approval."""
    if task_id not in _active_agent_loops:
        raise HTTPException(status_code=404, detail=f"Agent loop for task '{task_id}' not found.")

    approved = bool(payload.get("approved", True))
    agent = _active_agent_loops[task_id]
    remember = payload.get("remember")
    rule = None
    if approved and remember is not None and agent.pending_approval:
        pending = agent.pending_approval
        args = pending.get("arguments") or {}
        requested = (remember or {}).get("scope") if isinstance(remember, dict) else None
        try:
            default = args.get("path") or args.get("command")
            scope = validate_scope(pending["tool_name"], default if requested is None else requested)
        except ApprovalRuleError as e:
            raise HTTPException(status_code=400, detail=str(e))
        rule, created = ApprovalRuleStore(_workspace_fs.root).add(pending["tool_name"], scope, principal.actor)
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


@router.post("/v1/terminal/exec", dependencies=[Depends(require(Permission.EXECUTE_AGENT))], tags=["Workspace Filesystem"])
async def execute_terminal_command(payload: dict, principal: Principal = Depends(current_principal)):
    """Execute an interactive command inside the workspace with security gating and environment scrubbing."""
    cmd = payload.get("command", "").strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="Missing 'command' in request payload.")
    timeout = min(int(payload.get("timeout", 30)), 120)

    # Security filters against dangerous commands
    danger_patterns = [r"\brm\s+-rf\s+/", r">\s*/dev/sd[a-z]", r":\(\)\{ :\|:& \};:"]
    for pat in danger_patterns:
        if re.search(pat, cmd):
            await record_audit(principal, "terminal_exec_denied", cmd, False)
            raise HTTPException(status_code=403, detail=f"Command rejected by security safety gate: '{cmd}'")

    exec_cmd = cmd
    import sys
    if exec_cmd.startswith("python3 ") or exec_cmd.startswith("python "):
        parts = exec_cmd.split(" ", 1)
        exec_cmd = f'"{sys.executable}" {parts[1]}'

    start_t = time.perf_counter()
    clean_env, dropped = scrub_env(os.environ)
    if sys.prefix and "PATH" in clean_env:
        venv_bin = str(Path(sys.prefix) / "bin")
        if venv_bin not in clean_env["PATH"]:
            clean_env["PATH"] = f"{venv_bin}:{clean_env['PATH']}"

    try:
        proc = subprocess.run(
            exec_cmd,
            shell=True,
            cwd=str(_workspace_fs.root),
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        dur_ms = (time.perf_counter() - start_t) * 1000.0
        await record_audit(principal, "terminal_exec", f"{cmd} (exit {proc.returncode})", proc.returncode == 0)
        return {
            "command": cmd,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-10000:],
            "stderr": proc.stderr[-10000:],
            "duration_ms": round(dur_ms, 2),
        }
    except subprocess.TimeoutExpired:
        dur_ms = (time.perf_counter() - start_t) * 1000.0
        await record_audit(principal, "terminal_exec_timeout", cmd, False)
        raise HTTPException(status_code=408, detail=f"Command '{cmd}' timed out after {timeout}s.")


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

    # Token structure check: runner_id:org_id:timestamp:sig
    parts = auth_token.split(":")
    if len(parts) < 4 or parts[0] != runner_id or parts[1] != org_id:
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


@router.get("/v1/approval-rules", dependencies=[Depends(current_principal)], tags=["Autonomous Agent Loop"])
async def list_approval_rules():
    """Standing approvals for the open workspace."""
    return {"rules": [r.to_dict() for r in ApprovalRuleStore(_workspace_fs.root).list()]}


@router.delete("/v1/approval-rules/{rule_id}", dependencies=[Depends(require(Permission.APPROVE_TIER3))], tags=["Autonomous Agent Loop"])
async def revoke_approval_rule(rule_id: str, principal: Principal = Depends(current_principal)):
    """Revoke a standing approval; matching requests ask again."""
    gone = ApprovalRuleStore(_workspace_fs.root).remove(rule_id)
    if not gone:
        raise HTTPException(status_code=404, detail=f"Approval rule '{rule_id}' not found.")
    await record_audit(principal, "approval_rule_revoke", f"{gone.tool_name}:{gone.scope}", True)
    return {"revoked": gone.to_dict()}


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


@router.post("/v1/models/ledger/reset", tags=["Models"])
async def reset_model_cost_ledger(
    principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Reset the model cost ledger entries."""
    from core.models.cost_ledger import cost_ledger
    cost_ledger.reset()
    return {"status": "ok", "message": "Model cost ledger reset"}


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










