"""
FastAPI Routes for Kora AI Core.
"""

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, WebSocketException
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
from core.config import settings
from core.models.gateway import gateway
from core.security.origin import origin_allowed
from core.orchestration.state import validate_transition, InvalidStateTransitionError
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


@router.post("/v1/completions", response_model=CompletionResponseSchema, tags=["Inference"])
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


@router.post("/v1/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
async def create_task(
    request: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Create a new durable task."""
    task = TaskRecord(
        title=request.title,
        description=request.description,
        owner=request.owner,
        budget_usd=request.budget_usd,
        payload=request.payload,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    response = TaskResponse.model_validate(task)
    await _broadcast_task_state(response, previous_state=None)
    return response


@router.get("/v1/tasks", response_model=List[TaskResponse], tags=["Tasks"])
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


@router.get("/v1/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
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

    previous_state = task.state
    task.state = request.target_state
    await db.flush()
    await db.refresh(task)
    response = TaskResponse.model_validate(task)
    await _broadcast_task_state(response, previous_state=previous_state)
    return response


@router.post(
    "/v1/workflows/engineering-brief",
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


@router.get("/v1/memories", response_model=List[MemoryResponse], tags=["Memory"])
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


@router.post("/v1/memories", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED, tags=["Memory"])
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


@router.get("/v1/memories/{key}", response_model=MemoryResponse, tags=["Memory"])
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


@router.delete("/v1/memories/{key}", status_code=status.HTTP_204_NO_CONTENT, tags=["Memory"])
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
    """Manages active WebSocket connections for Kora Dev Studio."""
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
    """Real-time bidirectional channel for Kora Dev Studio events, diffs, and thought streaming."""
    if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host")):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Origin not allowed.")
    await ws_manager.connect(websocket)
    try:
        # Send initial connection handshake
        await websocket.send_json({
            "type": "handshake",
            "server": "Kora AI Dev Studio",
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
                new_state = data.get("enabled", True)
                gateway.air_gap.enabled = new_state
                await ws_manager.broadcast({
                    "type": "air_gap_status_changed",
                    "air_gapped": new_state,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            elif event_type == "execute_instruction":
                prompt = data.get("prompt", "")
                # Broadcast synthetic thinking / processing event
                await websocket.send_json({
                    "type": "agent_thinking",
                    "prompt": prompt,
                    "state": "EXECUTING",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            elif event_type == "run_self_healing":
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


@router.post("/v1/healing/repair", tags=["Autonomous Self-Healing"])
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


@router.post("/v1/payments/intent", tags=["Global Sovereign Settlement"])
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
    description = payload.get("description", "Kora Agent Service")

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


FLIGHT_RECORDINGS_DIR = Path(".kora/recordings")
# 243 + len(".flight.json") == 255, the common filesystem filename limit.
_TAPE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,243}$")


def _tape_path(task_id: str) -> Path:
    if not task_id or not _TAPE_ID_PATTERN.fullmatch(task_id) or ".." in task_id:
        raise HTTPException(status_code=400, detail="Invalid flight tape task_id.")
    return FLIGHT_RECORDINGS_DIR / f"{task_id}.flight.json"


@router.get("/v1/flight/tapes", tags=["Deterministic Flight Recorder"])
async def list_flight_tapes():
    """List all recorded deterministic agent execution tapes."""
    recordings_dir = FLIGHT_RECORDINGS_DIR
    if not recordings_dir.exists():
        return {"tapes": []}
    tapes = []
    for f in recordings_dir.glob("*.flight.json"):
        tapes.append({"task_id": f.name.replace(".flight.json", ""), "path": str(f)})
    return {"tapes": tapes}


@router.get("/v1/flight/tape/{task_id}", tags=["Deterministic Flight Recorder"])
async def get_flight_tape(task_id: str):
    """Retrieve full execution tape with all chronological step frames."""
    tape_file = _tape_path(task_id)
    if not tape_file.exists():
        raise HTTPException(status_code=404, detail=f"Flight tape for task {task_id} not found.")
    import json
    return json.loads(tape_file.read_text(encoding="utf-8"))


@router.post("/v1/flight/fork", tags=["Deterministic Flight Recorder"])
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
    return {
        "original_task_id": task_id,
        "forked_task_id": new_task_id,
        "forked_at_index": at_index,
        "tape_path": str(saved_path),
    }


@router.get("/v1/mesh/peers", tags=["Local Team Mesh"])
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

_workspace_fs = WorkspaceFilesystem()


@router.get("/v1/files/tree", tags=["Workspace Filesystem"])
async def get_workspace_file_tree(subpath: str = ".", max_depth: int = 4):
    """Retrieve recursive workspace file tree honoring .gitignore rules."""
    try:
        return _workspace_fs.get_file_tree(subpath=subpath, max_depth=max_depth)
    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/v1/files/content", tags=["Workspace Filesystem"])
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


@router.post("/v1/files/save", tags=["Workspace Filesystem"])
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


@router.get("/v1/git/status", tags=["Workspace Git"])
async def get_workspace_git_status():
    """Retrieve live Git repository status, branch, and modified files."""
    return _workspace_fs.get_git_status()


@router.get("/v1/git/diff", tags=["Workspace Git"])
async def get_workspace_git_diff(path: Optional[str] = None):
    """Retrieve live unified Git diff for workspace or specific file."""
    try:
        return _workspace_fs.get_git_diff(path=path)
    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))


# =====================================================================
# Codebase Semantic Index & RepoMap Endpoints
# =====================================================================

from core.storage.ast_index import CodebaseSemanticIndex

_semantic_index = CodebaseSemanticIndex(workspace_fs=_workspace_fs)


@router.get("/v1/index/repomap", tags=["Codebase Index"])
async def get_repository_map(max_tokens: int = 1500):
    """Retrieve condensed repository map for prompt context augmentation."""
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    return {
        "repo_map": _semantic_index.generate_repo_map(max_tokens=max_tokens),
        "total_files": len(_semantic_index.symbols),
    }


@router.get("/v1/index/search", tags=["Codebase Index"])
async def search_codebase_symbols(q: str, top_k: int = 10):
    """Perform hybrid semantic and lexical search across indexed codebase symbols."""
    if not _semantic_index.symbols:
        _semantic_index.index_workspace(max_files=150)
    return {
        "query": q,
        "results": _semantic_index.search_symbols(query=q, top_k=top_k),
    }


@router.post("/v1/index/refresh", tags=["Codebase Index"])
async def refresh_codebase_index(max_files: int = 200):
    """Re-index workspace files and refresh symbol embeddings."""
    res = _semantic_index.index_workspace(max_files=max_files)
    return {"status": "indexed", "stats": res}


# =====================================================================
# Autonomous ReAct Agent Loop Endpoints
# =====================================================================

from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy

_active_agent_loops: Dict[str, AutonomousAgentLoop] = {}


@router.post("/v1/agent/run", tags=["Autonomous Agent Loop"])
async def run_agent_task(payload: dict):
    """Initialize and run an autonomous agent engineering task."""
    task_id = payload.get("task_id") or f"task_{int(time.time())}"
    goal = payload.get("goal", "Inspect codebase and prepare solution")
    steps = payload.get("steps") or [
        "Inspect workspace files and dependencies",
        "Search codebase for target symbols",
        "Formulate and verify solution patch",
        "Run automated checks",
    ]
    policy_str = payload.get("policy", "confirm_mutation")
    policy = AutonomyPolicy(policy_str) if policy_str in [p.value for p in AutonomyPolicy] else AutonomyPolicy.CONFIRM_MUTATION

    agent = AutonomousAgentLoop(task_id=task_id, workspace_fs=_workspace_fs, policy=policy, record_flight=True)
    agent.initialize_plan(goal=goal, steps=steps)
    _active_agent_loops[task_id] = agent

    return {
        "task_id": task_id,
        "goal": goal,
        "policy": agent.policy.value,
        "state": agent.get_state(),
    }


@router.get("/v1/agent/status/{task_id}", tags=["Autonomous Agent Loop"])
async def get_agent_status(task_id: str):
    """Retrieve current state, plan steps, and pending approvals for an agent."""
    if task_id not in _active_agent_loops:
        raise HTTPException(status_code=404, detail=f"Agent loop for task '{task_id}' not found.")
    return _active_agent_loops[task_id].get_state()


@router.post("/v1/agent/step/{task_id}", tags=["Autonomous Agent Loop"])
async def step_agent_tool(task_id: str, payload: dict):
    """Execute a single tool call within the agent loop."""
    if task_id not in _active_agent_loops:
        raise HTTPException(status_code=404, detail=f"Agent loop for task '{task_id}' not found.")

    tool_name = payload.get("tool_name")
    arguments = payload.get("arguments", {})
    step_id = payload.get("step_id")

    if not tool_name:
        raise HTTPException(status_code=400, detail="Missing 'tool_name' in request payload.")

    agent = _active_agent_loops[task_id]
    try:
        res = await agent.execute_tool(tool_name=tool_name, arguments=arguments, step_id=step_id)
        return {
            "task_id": task_id,
            "step_result": res,
            "agent_state": agent.get_state(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/agent/approve/{task_id}", tags=["Autonomous Agent Loop"])
async def approve_agent_action(task_id: str, payload: dict):
    """Human-in-the-loop: grant or deny permission for a pending mutating tool."""
    if task_id not in _active_agent_loops:
        raise HTTPException(status_code=404, detail=f"Agent loop for task '{task_id}' not found.")

    approved = bool(payload.get("approved", True))
    agent = _active_agent_loops[task_id]
    res = await agent.approve_pending(approved=approved)
    return {
        "task_id": task_id,
        "approval_result": res,
        "agent_state": agent.get_state(),
    }







