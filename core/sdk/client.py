"""Keelway Client SDK — Programmatic Python Interface for Keelway Studio & Daemon."""
from typing import Optional, Dict, Any, List
import httpx
from core.sdk.errors import (
    KeelwayError,
    AuthenticationError,
    PermissionDeniedError,
    PolicyViolationError,
    TaskNotFoundError,
    AirGapEgressError,
    QuorumRequiredError,
    ConnectionError,
)


def _handle_response_error(res: httpx.Response):
    """Translates HTTP error status codes and JSON payloads into typed KeelwayError instances."""
    if res.is_success:
        return

    try:
        data = res.json()
        detail = data.get("detail", res.text)
    except Exception:
        detail = res.text

    msg = str(detail)
    status = res.status_code

    if status == 401:
        raise AuthenticationError(f"Authentication failed: {msg}", details={"status": status})
    elif status == 403:
        if "air-gap" in msg.lower() or "egress" in msg.lower():
            raise AirGapEgressError(f"Air-Gap zero-egress violation: {msg}", details={"status": status})
        elif "quorum" in msg.lower():
            raise QuorumRequiredError(f"Dual-human quorum required: {msg}", details={"status": status})
        raise PermissionDeniedError(f"Permission denied: {msg}", details={"status": status})
    elif status == 404:
        raise TaskNotFoundError(f"Resource not found: {msg}", details={"status": status})
    elif status == 422:
        raise PolicyViolationError(f"Policy validation failed: {msg}", details={"status": status})
    else:
        raise KeelwayError(f"HTTP {status}: {msg}", details={"status": status})


class AsyncKeelwayClient:
    """Asynchronous client for Keelway local daemon and multi-agent runtime."""

    def __init__(self, base_url: str = "http://127.0.0.1:7420", token: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        headers = {"User-Agent": "Keelway-SDK/0.71.0-beta"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=self.timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self._client.aclose()

    async def _req(self, method: str, path: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        try:
            res = await self._client.request(method, path, json=json, params=params)
        except httpx.ConnectError as e:
            raise ConnectionError(f"Failed to connect to Keelway daemon at {self.base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise ConnectionError(f"Keelway daemon request timed out: {e}") from e

        _handle_response_error(res)
        return res.json() if res.content else None

    # --- System & Pre-Flight ---
    async def get_health(self) -> Dict[str, Any]:
        """Fetch system health and database connectivity probe."""
        return await self._req("GET", "/health")

    async def get_status(self) -> Dict[str, Any]:
        """Fetch complete workspace status, git tree status, and air-gap state."""
        return await self._req("GET", "/v1/studio/status")

    async def run_doctor(self) -> Dict[str, Any]:
        """Execute sovereign enterprise system diagnostics across 7 dimensions."""
        return await self._req("GET", "/v1/doctor")

    async def get_sbom(self) -> Dict[str, Any]:
        """Fetch CycloneDX v1.5 Software Bill of Materials with HMAC provenance."""
        return await self._req("GET", "/v1/sbom")

    async def get_evidence_room(self) -> Dict[str, Any]:
        """Fetch live verified investor and enterprise audit evidence."""
        return await self._req("GET", "/v1/evidence/summary")

    # --- Tasks & Agent Workflow ---
    async def create_task(self, goal: str, policy: str = "ask_before_changes", model: Optional[str] = None, role: Optional[str] = None) -> Dict[str, Any]:
        """Create a new governed agent task."""
        body = {"title": goal, "description": goal, "policy": policy}
        if model:
            body["model"] = model
        if role:
            body["role"] = role
        return await self._req("POST", "/v1/tasks", json=body)

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Retrieve state and activity trace for an existing task."""
        return await self._req("GET", f"/v1/tasks/{task_id}")

    async def list_tasks(self) -> List[Dict[str, Any]]:
        """List all active and completed tasks."""
        res = await self._req("GET", "/v1/tasks")
        return res if isinstance(res, list) else res.get("tasks", [])

    async def step_agent(self, task_id: str) -> Dict[str, Any]:
        """Trigger an incremental step execution on an active task."""
        return await self._req("POST", f"/v1/agent/step/{task_id}")

    async def approve_step(self, task_id: str, decision: str = "allow", feedback: str = "") -> Dict[str, Any]:
        """Approve or deny an action gated on human permission."""
        return await self._req("POST", f"/v1/agent/approve/{task_id}", json={"decision": decision, "feedback": feedback})

    # --- Flight Recorder & Time-Travel ---
    async def list_flight_tapes(self) -> List[Dict[str, Any]]:
        """List all sealed and active flight recorder tapes."""
        res = await self._req("GET", "/v1/flight/tapes")
        return res if isinstance(res, list) else res.get("tapes", [])

    async def get_flight_tape(self, task_id: str) -> Dict[str, Any]:
        """Retrieve full event sequence and cryptographic digest for a flight tape."""
        return await self._req("GET", f"/v1/flight/tape/{task_id}")

    async def fork_flight_tape(self, task_id: str, checkpoint_index: int, new_branch_name: Optional[str] = None, extract_worktree: bool = True) -> Dict[str, Any]:
        """Fork a flight tape from a historical checkpoint into an isolated git worktree."""
        body = {"checkpoint_index": checkpoint_index, "extract_worktree": extract_worktree}
        if new_branch_name:
            body["new_branch_name"] = new_branch_name
        return await self._req("POST", f"/v1/flight/tape/{task_id}/fork", json=body)

    # --- Codebase Intelligence ---
    async def search_codebase(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search symbols and references across the project AST graph."""
        return await self._req("GET", "/v1/codebase/symbols", params={"query": query, "limit": limit})

    async def get_code_hierarchy(self, file_path: str) -> Dict[str, Any]:
        """Extract classes, functions, and import dependencies for a file."""
        return await self._req("GET", "/v1/codebase/hierarchy", params={"file_path": file_path})

    # --- Scoped Memory & DLP ---
    async def record_fact(self, key: str, statement: str, scope: str = "PROJECT") -> Dict[str, Any]:
        """Record a knowledge fact subject to regex DLP scanning."""
        return await self._req("POST", "/v1/memories", json={"key": key, "content": statement, "scope": scope})

    async def query_facts(self, scope: Optional[str] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query scoped facts."""
        params = {}
        if scope:
            params["scope"] = scope
        if query:
            params["query"] = query
        res = await self._req("GET", "/v1/memories", params=params)
        return res if isinstance(res, list) else res.get("memories", [])

    # --- Self-Healing Test & Repair ---
    async def execute_self_healing(self, test_command: str = "pytest -q", max_attempts: int = 3) -> Dict[str, Any]:
        """Execute closed-loop test execution and automated AST surgical repair."""
        return await self._req("POST", "/v1/healing/repair", json={"test_command": test_command, "attempts": max_attempts})


class KeelwayClient:
    """Synchronous client wrapper for Keelway local daemon and multi-agent runtime."""

    def __init__(self, base_url: str = "http://127.0.0.1:7420", token: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        headers = {"User-Agent": "Keelway-SDK/0.71.0-beta"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=self.timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._client.close()

    def _req(self, method: str, path: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        try:
            res = self._client.request(method, path, json=json, params=params)
        except httpx.ConnectError as e:
            raise ConnectionError(f"Failed to connect to Keelway daemon at {self.base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise ConnectionError(f"Keelway daemon request timed out: {e}") from e

        _handle_response_error(res)
        return res.json() if res.content else None

    # --- System & Pre-Flight ---
    def get_health(self) -> Dict[str, Any]:
        return self._req("GET", "/health")

    def get_status(self) -> Dict[str, Any]:
        return self._req("GET", "/v1/studio/status")

    def run_doctor(self) -> Dict[str, Any]:
        return self._req("GET", "/v1/doctor")

    def get_sbom(self) -> Dict[str, Any]:
        return self._req("GET", "/v1/sbom")

    def get_evidence_room(self) -> Dict[str, Any]:
        return self._req("GET", "/v1/evidence/summary")

    # --- Tasks & Agent Workflow ---
    def create_task(self, goal: str, policy: str = "ask_before_changes", model: Optional[str] = None, role: Optional[str] = None) -> Dict[str, Any]:
        body = {"title": goal, "description": goal, "policy": policy}
        if model:
            body["model"] = model
        if role:
            body["role"] = role
        return self._req("POST", "/v1/tasks", json=body)

    def get_task(self, task_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/v1/tasks/{task_id}")

    def list_tasks(self) -> List[Dict[str, Any]]:
        res = self._req("GET", "/v1/tasks")
        return res if isinstance(res, list) else res.get("tasks", [])

    def step_agent(self, task_id: str) -> Dict[str, Any]:
        return self._req("POST", f"/v1/agent/step/{task_id}")

    def approve_step(self, task_id: str, decision: str = "allow", feedback: str = "") -> Dict[str, Any]:
        return self._req("POST", f"/v1/agent/approve/{task_id}", json={"decision": decision, "feedback": feedback})

    # --- Flight Recorder & Time-Travel ---
    def list_flight_tapes(self) -> List[Dict[str, Any]]:
        res = self._req("GET", "/v1/flight/tapes")
        return res if isinstance(res, list) else res.get("tapes", [])

    def get_flight_tape(self, task_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/v1/flight/tape/{task_id}")

    def fork_flight_tape(self, task_id: str, checkpoint_index: int, new_branch_name: Optional[str] = None, extract_worktree: bool = True) -> Dict[str, Any]:
        body = {"checkpoint_index": checkpoint_index, "extract_worktree": extract_worktree}
        if new_branch_name:
            body["new_branch_name"] = new_branch_name
        return self._req("POST", f"/v1/flight/tape/{task_id}/fork", json=body)

    # --- Codebase Intelligence ---
    def search_codebase(self, query: str, limit: int = 10) -> Dict[str, Any]:
        return self._req("GET", "/v1/codebase/symbols", params={"query": query, "limit": limit})

    def get_code_hierarchy(self, file_path: str) -> Dict[str, Any]:
        return self._req("GET", "/v1/codebase/hierarchy", params={"file_path": file_path})

    # --- Scoped Memory & DLP ---
    def record_fact(self, key: str, statement: str, scope: str = "PROJECT") -> Dict[str, Any]:
        return self._req("POST", "/v1/memories", json={"key": key, "content": statement, "scope": scope})

    def query_facts(self, scope: Optional[str] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if scope:
            params["scope"] = scope
        if query:
            params["query"] = query
        res = self._req("GET", "/v1/memories", params=params)
        return res if isinstance(res, list) else res.get("memories", [])

    # --- Self-Healing Test & Repair ---
    def execute_self_healing(self, test_command: str = "pytest -q", max_attempts: int = 3) -> Dict[str, Any]:
        return self._req("POST", "/v1/healing/repair", json={"test_command": test_command, "attempts": max_attempts})
