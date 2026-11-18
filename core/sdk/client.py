"""Keelway Client SDK — Programmatic Python Interface for Keelway Unified AI Platform, Studio & Daemon."""
from typing import Optional, Dict, Any, List, AsyncIterator, Iterator, Union
import json as _json
import httpx
from core.sdk.errors import (
    KeelwayError,
    AuthenticationError,
    PermissionDeniedError,
    PolicyViolationError,
    TaskNotFoundError,
    AirGapEgressError,
    QuorumRequiredError,
    BudgetExceededError,
    RateLimitExceededError,
    ConnectionError,
)
from core.sdk.cluster_client import AsyncClusterClient, SyncClusterClient
from core.sdk.platform_client import AsyncPlatformClient, SyncPlatformClient


def _handle_response_error(res: httpx.Response):
    """Translates HTTP error status codes and JSON payloads into typed KeelwayError instances."""
    if res.is_success:
        return

    try:
        data = res.json()
        detail = data.get("detail", res.text) if isinstance(data, dict) else res.text
    except Exception:
        detail = res.text

    msg = str(detail)
    status = res.status_code
    err_details: Dict[str, Any] = {**detail, "status": status} if isinstance(detail, dict) else {"status": status}

    if status == 401:
        raise AuthenticationError(f"Authentication failed: {msg}", details=err_details)
    elif status == 402:
        raise BudgetExceededError(f"Budget exceeded: {msg}", details=err_details)
    elif status == 403:
        if "air-gap" in msg.lower() or "egress" in msg.lower():
            raise AirGapEgressError(f"Air-Gap zero-egress violation: {msg}", details=err_details)
        elif "quorum" in msg.lower():
            raise QuorumRequiredError(f"Dual-human quorum required: {msg}", details=err_details)
        raise PermissionDeniedError(f"Permission denied: {msg}", details=err_details)
    elif status == 404:
        raise TaskNotFoundError(f"Resource not found: {msg}", details=err_details)
    elif status == 422:
        raise PolicyViolationError(f"Policy validation failed: {msg}", details=err_details)
    elif status == 429:
        raise RateLimitExceededError(f"Rate limit exceeded: {msg}", details=err_details)
    else:
        raise KeelwayError(f"HTTP {status}: {msg}", details=err_details)


def _normalize_messages(messages: Union[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    return messages


def _build_chat_payload(
    messages: Union[str, List[Dict[str, Any]]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    response_format: Optional[Dict[str, Any]] = None,
    privacy_level: str = "standard",
    required_capabilities: Optional[List[str]] = None,
    max_cost_usd: Optional[float] = None,
    stream: bool = False,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "messages": _normalize_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "privacy_level": privacy_level,
        "stream": stream,
    }
    if model is not None:
        body["model"] = model
    if response_format is not None:
        body["response_format"] = response_format
    if required_capabilities is not None:
        body["required_capabilities"] = required_capabilities
    if max_cost_usd is not None:
        body["max_cost_usd"] = max_cost_usd
    return body


def _build_response_payload(
    input_data: Any,
    model: Optional[str] = None,
    instructions: Optional[str] = None,
    previous_response_id: Optional[str] = None,
    speculative: bool = False,
    privacy_level: str = "standard",
    text: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "input": input_data,
        "speculative": speculative,
        "privacy_level": privacy_level,
    }
    if model is not None:
        body["model"] = model
    if instructions is not None:
        body["instructions"] = instructions
    if previous_response_id is not None:
        body["previous_response_id"] = previous_response_id
    if text is not None:
        body["text"] = text
    return body


def _build_route_explain_payload(
    messages: Union[str, List[Dict[str, Any]]],
    model: Optional[str] = None,
    privacy_level: str = "standard",
    required_capabilities: Optional[List[str]] = None,
    max_cost_usd: Optional[float] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "messages": _normalize_messages(messages),
        "privacy_level": privacy_level,
    }
    if model is not None:
        body["model"] = model
    if required_capabilities is not None:
        body["required_capabilities"] = required_capabilities
    if max_cost_usd is not None:
        body["max_cost_usd"] = max_cost_usd
    return body


class AsyncKeelwayClient:
    """Asynchronous client for Keelway Unified AI Platform, local daemon, and multi-agent runtime."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:7420",
        token: Optional[str] = None,
        timeout: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        headers = {"User-Agent": "Keelway-SDK/1.0.0"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
            transport=transport,
        )
        self.platform = AsyncPlatformClient(self)
        self.cluster = AsyncClusterClient(self)

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
        body: Dict[str, Any] = {"checkpoint_index": checkpoint_index, "extract_worktree": extract_worktree}
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
        params: Dict[str, Any] = {}
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

    # --- Unified AI Platform v1: Models & Usage ---
    async def list_models(
        self,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Discover models across Open-Weight and Closed Frontier providers."""
        params: Dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        if provider is not None:
            params["provider"] = provider
        if capability is not None:
            params["capability"] = capability
        return await self._req("GET", "/v1/models", params=params or None)

    async def get_usage(self) -> Dict[str, Any]:
        """Retrieve aggregate usage telemetry, Sovereign Efficiency Index, and cost ledger."""
        return await self._req("GET", "/v1/usage")

    # --- Unified AI Platform v1: Chat Completions & Streaming ---
    async def chat_complete(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, Any]] = None,
        privacy_level: str = "standard",
        required_capabilities: Optional[List[str]] = None,
        max_cost_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute an OpenAI-compatible hybrid chat completion."""
        body = _build_chat_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            privacy_level=privacy_level,
            required_capabilities=required_capabilities,
            max_cost_usd=max_cost_usd,
            stream=False,
        )
        return await self._req("POST", "/v1/chat/completions", json=body)

    async def stream_chat(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, Any]] = None,
        privacy_level: str = "standard",
        required_capabilities: Optional[List[str]] = None,
        max_cost_usd: Optional[float] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream SSE chat completion chunks, stopping cleanly at [DONE]."""
        body = _build_chat_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            privacy_level=privacy_level,
            required_capabilities=required_capabilities,
            max_cost_usd=max_cost_usd,
            stream=True,
        )
        try:
            async with self._client.stream("POST", "/v1/chat/completions", json=body) as res:
                if not res.is_success:
                    await res.aread()
                    _handle_response_error(res)
                async for line in res.aiter_lines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith(":"):
                        continue
                    if stripped.startswith("data:"):
                        data_str = stripped[5:].strip()
                        if data_str == "[DONE]":
                            break
                        yield _json.loads(data_str)
        except httpx.ConnectError as e:
            raise ConnectionError(f"Failed to connect to Keelway daemon at {self.base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise ConnectionError(f"Keelway daemon request timed out: {e}") from e

    # --- Unified AI Platform v1: Stateful Responses API ---
    async def create_response(
        self,
        input_data: Any,
        model: Optional[str] = None,
        instructions: Optional[str] = None,
        previous_response_id: Optional[str] = None,
        speculative: bool = False,
        privacy_level: str = "standard",
        text: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a stateful Unified AI response with optional turn chaining and speculative decoding."""
        body = _build_response_payload(
            input_data=input_data,
            model=model,
            instructions=instructions,
            previous_response_id=previous_response_id,
            speculative=speculative,
            privacy_level=privacy_level,
            text=text,
        )
        return await self._req("POST", "/v1/responses", json=body)

    async def get_response(self, response_id: str) -> Dict[str, Any]:
        """Retrieve a previously stored response by ID."""
        return await self._req("GET", f"/v1/responses/{response_id}")

    # --- Unified AI Platform v1: Routing Inspector ---
    async def explain_route(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        model: Optional[str] = None,
        privacy_level: str = "standard",
        required_capabilities: Optional[List[str]] = None,
        max_cost_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Inspect 4-way provenance split and fallback chain for a candidate request."""
        body = _build_route_explain_payload(
            messages=messages,
            model=model,
            privacy_level=privacy_level,
            required_capabilities=required_capabilities,
            max_cost_usd=max_cost_usd,
        )
        return await self._req("POST", "/v1/routing/explain", json=body)

    # --- Unified AI Platform v1: OpenCore Subsystem ---
    async def opencore_status(self) -> Dict[str, Any]:
        """Retrieve OpenCore hardware detection and cluster VRAM telemetry."""
        return await self._req("GET", "/v1/opencore/status")

    async def opencore_weights(self) -> List[Dict[str, Any]]:
        """List OpenCore weight manifests and local cache state."""
        return await self._req("GET", "/v1/opencore/weights")

    async def opencore_load_model(
        self,
        model_id: str,
        quantization: Optional[str] = None,
        backend: str = "mock",
    ) -> Dict[str, Any]:
        """Load an OpenCore checkpoint into accelerator memory."""
        body: Dict[str, Any] = {"model_id": model_id, "backend": backend}
        if quantization is not None:
            body["quantization"] = quantization
        return await self._req("POST", "/v1/opencore/models/load", json=body)

    async def opencore_unload_model(self, model_id: str) -> Dict[str, Any]:
        """Unload an OpenCore checkpoint from accelerator memory."""
        return await self._req("POST", "/v1/opencore/models/unload", json={"model_id": model_id})

    async def opencore_modelfile(
        self,
        model_id: str,
        base_source: str = "qwen3.5:latest",
        quantization: str = "q4_k_m",
        adapter_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a reproducible Sovereign Modelfile for an OpenCore checkpoint."""
        body: Dict[str, Any] = {
            "model_id": model_id,
            "base_source": base_source,
            "quantization": quantization,
        }
        if adapter_id is not None:
            body["adapter_id"] = adapter_id
        return await self._req("POST", "/v1/opencore/modelfile", json=body)

    async def opencore_adapt_recipe(
        self,
        base_model_id: str = "keelway-core:7b",
        task: str = "multilingual_localization",
        target_languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate sovereign PEFT/Unsloth adaptation recipes and multilingual samples."""
        body: Dict[str, Any] = {"base_model_id": base_model_id, "task": task}
        if target_languages is not None:
            body["target_languages"] = [lang.lower() for lang in target_languages]
        return await self._req("POST", "/v1/opencore/adapt/recipe", json=body)

    # --- Unified AI Platform v1: Governance & Swarm ---
    async def create_tenant(self, tenant_id: str, name: str, **policy_kwargs: Any) -> Dict[str, Any]:
        """Register or update a multi-tenant governance policy and spend cap."""
        body: Dict[str, Any] = {"tenant_id": tenant_id, "name": name, **policy_kwargs}
        return await self._req("POST", "/v1/governance/tenants", json=body)

    async def issue_api_key(
        self,
        tenant_id: str,
        name: str,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Issue a scoped kw_live_* API key bound to a tenant."""
        body: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "name": name,
            "scopes": scopes if scopes is not None else ["models:read", "inference:write"],
        }
        return await self._req("POST", "/v1/governance/keys", json=body)

    async def evaluate_governance(self, **kwargs: Any) -> Dict[str, Any]:
        """Simulate pre-flight tenant budget, scope, and data residency enforcement."""
        return await self._req("POST", "/v1/governance/evaluate", json=kwargs)

    async def get_governance_audit(self) -> Dict[str, Any]:
        """Retrieve and verify the SHA-256 hash-chained governance audit log."""
        return await self._req("GET", "/v1/governance/audit")

    async def run_swarm(
        self,
        seed_text: str,
        simulation_goal: str,
        entities_spec: List[Dict[str, Any]],
        rounds: int = 2,
        mode: str = "mock",
    ) -> Dict[str, Any]:
        """Execute a MiroFish × Keelway multi-agent OASIS social prediction swarm."""
        body: Dict[str, Any] = {
            "seed_text": seed_text,
            "simulation_goal": simulation_goal,
            "entities_spec": entities_spec,
            "rounds": rounds,
            "mode": mode,
        }
        return await self._req("POST", "/v1/eval/swarm", json=body)


class KeelwayClient:
    """Synchronous client wrapper for Keelway Unified AI Platform, local daemon, and multi-agent runtime."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:7420",
        token: Optional[str] = None,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        headers = {"User-Agent": "Keelway-SDK/1.0.0"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
            transport=transport,
        )
        self.platform = SyncPlatformClient(self)
        self.cluster = SyncClusterClient(self)

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
        body: Dict[str, Any] = {"checkpoint_index": checkpoint_index, "extract_worktree": extract_worktree}
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
        params: Dict[str, Any] = {}
        if scope:
            params["scope"] = scope
        if query:
            params["query"] = query
        res = self._req("GET", "/v1/memories", params=params)
        return res if isinstance(res, list) else res.get("memories", [])

    # --- Self-Healing Test & Repair ---
    def execute_self_healing(self, test_command: str = "pytest -q", max_attempts: int = 3) -> Dict[str, Any]:
        return self._req("POST", "/v1/healing/repair", json={"test_command": test_command, "attempts": max_attempts})

    # --- Unified AI Platform v1: Models & Usage ---
    def list_models(
        self,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        if provider is not None:
            params["provider"] = provider
        if capability is not None:
            params["capability"] = capability
        return self._req("GET", "/v1/models", params=params or None)

    def get_usage(self) -> Dict[str, Any]:
        return self._req("GET", "/v1/usage")

    # --- Unified AI Platform v1: Chat Completions & Streaming ---
    def chat_complete(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, Any]] = None,
        privacy_level: str = "standard",
        required_capabilities: Optional[List[str]] = None,
        max_cost_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        body = _build_chat_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            privacy_level=privacy_level,
            required_capabilities=required_capabilities,
            max_cost_usd=max_cost_usd,
            stream=False,
        )
        return self._req("POST", "/v1/chat/completions", json=body)

    def stream_chat(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, Any]] = None,
        privacy_level: str = "standard",
        required_capabilities: Optional[List[str]] = None,
        max_cost_usd: Optional[float] = None,
    ) -> Iterator[Dict[str, Any]]:
        body = _build_chat_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            privacy_level=privacy_level,
            required_capabilities=required_capabilities,
            max_cost_usd=max_cost_usd,
            stream=True,
        )
        try:
            with self._client.stream("POST", "/v1/chat/completions", json=body) as res:
                if not res.is_success:
                    res.read()
                    _handle_response_error(res)
                for line in res.iter_lines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith(":"):
                        continue
                    if stripped.startswith("data:"):
                        data_str = stripped[5:].strip()
                        if data_str == "[DONE]":
                            break
                        yield _json.loads(data_str)
        except httpx.ConnectError as e:
            raise ConnectionError(f"Failed to connect to Keelway daemon at {self.base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise ConnectionError(f"Keelway daemon request timed out: {e}") from e

    # --- Unified AI Platform v1: Stateful Responses API ---
    def create_response(
        self,
        input_data: Any,
        model: Optional[str] = None,
        instructions: Optional[str] = None,
        previous_response_id: Optional[str] = None,
        speculative: bool = False,
        privacy_level: str = "standard",
        text: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = _build_response_payload(
            input_data=input_data,
            model=model,
            instructions=instructions,
            previous_response_id=previous_response_id,
            speculative=speculative,
            privacy_level=privacy_level,
            text=text,
        )
        return self._req("POST", "/v1/responses", json=body)

    def get_response(self, response_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/v1/responses/{response_id}")

    # --- Unified AI Platform v1: Routing Inspector ---
    def explain_route(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        model: Optional[str] = None,
        privacy_level: str = "standard",
        required_capabilities: Optional[List[str]] = None,
        max_cost_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        body = _build_route_explain_payload(
            messages=messages,
            model=model,
            privacy_level=privacy_level,
            required_capabilities=required_capabilities,
            max_cost_usd=max_cost_usd,
        )
        return self._req("POST", "/v1/routing/explain", json=body)

    # --- Unified AI Platform v1: OpenCore Subsystem ---
    def opencore_status(self) -> Dict[str, Any]:
        return self._req("GET", "/v1/opencore/status")

    def opencore_weights(self) -> List[Dict[str, Any]]:
        return self._req("GET", "/v1/opencore/weights")

    def opencore_load_model(
        self,
        model_id: str,
        quantization: Optional[str] = None,
        backend: str = "mock",
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"model_id": model_id, "backend": backend}
        if quantization is not None:
            body["quantization"] = quantization
        return self._req("POST", "/v1/opencore/models/load", json=body)

    def opencore_unload_model(self, model_id: str) -> Dict[str, Any]:
        return self._req("POST", "/v1/opencore/models/unload", json={"model_id": model_id})

    def opencore_modelfile(
        self,
        model_id: str,
        base_source: str = "qwen3.5:latest",
        quantization: str = "q4_k_m",
        adapter_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model_id": model_id,
            "base_source": base_source,
            "quantization": quantization,
        }
        if adapter_id is not None:
            body["adapter_id"] = adapter_id
        return self._req("POST", "/v1/opencore/modelfile", json=body)

    def opencore_adapt_recipe(
        self,
        base_model_id: str = "keelway-core:7b",
        task: str = "multilingual_localization",
        target_languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"base_model_id": base_model_id, "task": task}
        if target_languages is not None:
            body["target_languages"] = [lang.lower() for lang in target_languages]
        return self._req("POST", "/v1/opencore/adapt/recipe", json=body)

    # --- Unified AI Platform v1: Governance & Swarm ---
    def create_tenant(self, tenant_id: str, name: str, **policy_kwargs: Any) -> Dict[str, Any]:
        body: Dict[str, Any] = {"tenant_id": tenant_id, "name": name, **policy_kwargs}
        return self._req("POST", "/v1/governance/tenants", json=body)

    def issue_api_key(
        self,
        tenant_id: str,
        name: str,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "name": name,
            "scopes": scopes if scopes is not None else ["models:read", "inference:write"],
        }
        return self._req("POST", "/v1/governance/keys", json=body)

    def evaluate_governance(self, **kwargs: Any) -> Dict[str, Any]:
        return self._req("POST", "/v1/governance/evaluate", json=kwargs)

    def get_governance_audit(self) -> Dict[str, Any]:
        return self._req("GET", "/v1/governance/audit")

    def run_swarm(
        self,
        seed_text: str,
        simulation_goal: str,
        entities_spec: List[Dict[str, Any]],
        rounds: int = 2,
        mode: str = "mock",
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "seed_text": seed_text,
            "simulation_goal": simulation_goal,
            "entities_spec": entities_spec,
            "rounds": rounds,
            "mode": mode,
        }
        return self._req("POST", "/v1/eval/swarm", json=body)
