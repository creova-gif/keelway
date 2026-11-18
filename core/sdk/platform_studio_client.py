"""
Keelway Client SDK — Phase 12 Golden-Thread Bidirectional KFlow Studio,
Sandbox Blast-Radius Radar & Prompt Regression Gate Mixins (`client.platform`).

Defines `AsyncPlatformStudioMixin` and `SyncPlatformStudioMixin` inherited by
`AsyncPlatformRuntimeMixin` and `SyncPlatformRuntimeMixin` for 100% sync + async parity across
`/v1/platform/studio/kflow/sync`, `/v1/platform/studio/blast-radius*`, and `/v1/platform/studio/prompt-gate/*`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient

_VALID_STUDIO_DIRECTIONS = ("code_to_graph", "graph_to_code")
_VALID_STUDIO_LANGUAGES = ("python", "typescript")


def _studio_kflow_sync_body(
    direction: str,
    workspace_id: str,
    language: str,
    workflow_id: str,
    source_code: Optional[str],
    nodes: Optional[List[Dict[str, Any]]],
    persist: Optional[bool],
) -> Dict[str, Any]:
    clean_direction = str(direction or "").strip()
    if clean_direction not in _VALID_STUDIO_DIRECTIONS:
        raise ValueError("direction must be 'code_to_graph' or 'graph_to_code'.")
    clean_language = str(language or "").strip()
    if clean_language not in _VALID_STUDIO_LANGUAGES:
        raise ValueError("language must be 'python' or 'typescript'.")
    clean_wf = str(workflow_id or "").strip()
    if not clean_wf:
        raise ValueError("workflow_id must be non-empty.")
    body: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "direction": clean_direction,
        "language": clean_language,
        "workflow_id": clean_wf,
    }
    if source_code is not None:
        body["source_code"] = source_code
    if nodes is not None:
        body["nodes"] = [dict(node) for node in nodes]
    if persist is not None:
        body["persist"] = bool(persist)
    return body


def _studio_blast_radius_body(
    workspace_id: str,
    trace_id: Optional[str],
    workflow_id: Optional[str],
    fs_reads: Optional[List[str]],
    fs_writes: Optional[List[str]],
    blocked_paths: Optional[List[str]],
    egress_attempts: Optional[int],
    blocked_egress_hosts: Optional[List[str]],
    p10_gates_triggered: Optional[int],
    seatbelted: Optional[bool],
) -> Dict[str, Any]:
    if egress_attempts is not None and int(egress_attempts) < 0:
        raise ValueError("egress_attempts must be >= 0.")
    if p10_gates_triggered is not None and int(p10_gates_triggered) < 0:
        raise ValueError("p10_gates_triggered must be >= 0.")
    body: Dict[str, Any] = {"workspace_id": workspace_id}
    if trace_id is not None and str(trace_id).strip():
        body["trace_id"] = str(trace_id).strip()
    if workflow_id is not None and str(workflow_id).strip():
        body["workflow_id"] = str(workflow_id).strip()
    if fs_reads is not None:
        body["fs_reads"] = list(fs_reads)
    if fs_writes is not None:
        body["fs_writes"] = list(fs_writes)
    if blocked_paths is not None:
        body["blocked_paths"] = list(blocked_paths)
    if egress_attempts is not None:
        body["egress_attempts"] = int(egress_attempts)
    if blocked_egress_hosts is not None:
        body["blocked_egress_hosts"] = list(blocked_egress_hosts)
    if p10_gates_triggered is not None:
        body["p10_gates_triggered"] = int(p10_gates_triggered)
    if seatbelted is not None:
        body["seatbelted"] = bool(seatbelted)
    return body


def _studio_blast_radius_list_params(workspace_id: str, trace_id: Optional[str], limit: int) -> Dict[str, Any]:
    if int(limit) < 1:
        raise ValueError("limit must be >= 1.")
    params: Dict[str, Any] = {"workspace_id": workspace_id, "limit": int(limit)}
    if trace_id is not None and str(trace_id).strip():
        params["trace_id"] = str(trace_id).strip()
    return params


def _studio_prompt_gate_eval_body(
    candidate_prompt_version: str,
    candidate_model_id: str,
    workspace_id: str,
    candidate_prompt_text: Optional[str],
    required_json_keys: Optional[List[str]],
    min_pass_rate: Optional[float],
) -> Dict[str, Any]:
    clean_ver = str(candidate_prompt_version or "").strip()
    if not clean_ver:
        raise ValueError("candidate_prompt_version must be non-empty.")
    clean_model = str(candidate_model_id or "").strip()
    if not clean_model:
        raise ValueError("candidate_model_id must be non-empty.")
    body: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "candidate_prompt_version": clean_ver,
        "candidate_model_id": clean_model,
    }
    if candidate_prompt_text is not None:
        body["candidate_prompt_text"] = candidate_prompt_text
    if required_json_keys is not None:
        body["required_json_keys"] = list(required_json_keys)
    if min_pass_rate is not None:
        rate = float(min_pass_rate)
        if rate < 0.0 or rate > 1.0:
            raise ValueError("min_pass_rate must be between 0.0 and 1.0.")
        body["min_pass_rate"] = rate
    return body


def _studio_prompt_gate_list_params(workspace_id: str, limit: int) -> Dict[str, Any]:
    if int(limit) < 1:
        raise ValueError("limit must be >= 1.")
    return {"workspace_id": workspace_id, "limit": int(limit)}


class AsyncPlatformStudioMixin:
    """Asynchronous Phase 12 Bidirectional KFlow Studio, Blast-Radius & Prompt Gate methods."""

    _client: "AsyncKeelwayClient"

    async def sync_kflow_studio(
        self,
        direction: str = "code_to_graph",
        *,
        workspace_id: str = "default",
        language: str = "python",
        workflow_id: str = "WF-STUDIO-01",
        source_code: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        persist: Optional[bool] = None,
    ) -> Dict[str, Any]:
        body = _studio_kflow_sync_body(direction, workspace_id, language, workflow_id, source_code, nodes, persist)
        return await self._client._req("POST", "/v1/platform/studio/kflow/sync", json=body)

    async def record_blast_radius(
        self,
        *,
        workspace_id: str = "default",
        trace_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        fs_reads: Optional[List[str]] = None,
        fs_writes: Optional[List[str]] = None,
        blocked_paths: Optional[List[str]] = None,
        egress_attempts: Optional[int] = None,
        blocked_egress_hosts: Optional[List[str]] = None,
        p10_gates_triggered: Optional[int] = None,
        seatbelted: Optional[bool] = None,
    ) -> Dict[str, Any]:
        body = _studio_blast_radius_body(
            workspace_id, trace_id, workflow_id, fs_reads, fs_writes,
            blocked_paths, egress_attempts, blocked_egress_hosts, p10_gates_triggered, seatbelted,
        )
        return await self._client._req("POST", "/v1/platform/studio/blast-radius/record", json=body)

    async def list_blast_radius_audits(
        self, workspace_id: str = "default", trace_id: Optional[str] = None, limit: int = 25
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET", "/v1/platform/studio/blast-radius", params=_studio_blast_radius_list_params(workspace_id, trace_id, limit)
        )

    async def evaluate_prompt_gate(
        self,
        candidate_prompt_version: str,
        candidate_model_id: str,
        *,
        workspace_id: str = "default",
        candidate_prompt_text: Optional[str] = None,
        required_json_keys: Optional[List[str]] = None,
        min_pass_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        body = _studio_prompt_gate_eval_body(
            candidate_prompt_version, candidate_model_id, workspace_id, candidate_prompt_text, required_json_keys, min_pass_rate
        )
        return await self._client._req("POST", "/v1/platform/studio/prompt-gate/evaluate", json=body)

    async def list_prompt_gate_runs(self, workspace_id: str = "default", limit: int = 20) -> Dict[str, Any]:
        return await self._client._req(
            "GET", "/v1/platform/studio/prompt-gate/runs", params=_studio_prompt_gate_list_params(workspace_id, limit)
        )


class SyncPlatformStudioMixin:
    """Synchronous Phase 12 Bidirectional KFlow Studio, Blast-Radius & Prompt Gate methods."""

    _client: "KeelwayClient"

    def sync_kflow_studio(
        self,
        direction: str = "code_to_graph",
        *,
        workspace_id: str = "default",
        language: str = "python",
        workflow_id: str = "WF-STUDIO-01",
        source_code: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        persist: Optional[bool] = None,
    ) -> Dict[str, Any]:
        body = _studio_kflow_sync_body(direction, workspace_id, language, workflow_id, source_code, nodes, persist)
        return self._client._req("POST", "/v1/platform/studio/kflow/sync", json=body)

    def record_blast_radius(
        self,
        *,
        workspace_id: str = "default",
        trace_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        fs_reads: Optional[List[str]] = None,
        fs_writes: Optional[List[str]] = None,
        blocked_paths: Optional[List[str]] = None,
        egress_attempts: Optional[int] = None,
        blocked_egress_hosts: Optional[List[str]] = None,
        p10_gates_triggered: Optional[int] = None,
        seatbelted: Optional[bool] = None,
    ) -> Dict[str, Any]:
        body = _studio_blast_radius_body(
            workspace_id, trace_id, workflow_id, fs_reads, fs_writes,
            blocked_paths, egress_attempts, blocked_egress_hosts, p10_gates_triggered, seatbelted,
        )
        return self._client._req("POST", "/v1/platform/studio/blast-radius/record", json=body)

    def list_blast_radius_audits(
        self, workspace_id: str = "default", trace_id: Optional[str] = None, limit: int = 25
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET", "/v1/platform/studio/blast-radius", params=_studio_blast_radius_list_params(workspace_id, trace_id, limit)
        )

    def evaluate_prompt_gate(
        self,
        candidate_prompt_version: str,
        candidate_model_id: str,
        *,
        workspace_id: str = "default",
        candidate_prompt_text: Optional[str] = None,
        required_json_keys: Optional[List[str]] = None,
        min_pass_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        body = _studio_prompt_gate_eval_body(
            candidate_prompt_version, candidate_model_id, workspace_id, candidate_prompt_text, required_json_keys, min_pass_rate
        )
        return self._client._req("POST", "/v1/platform/studio/prompt-gate/evaluate", json=body)

    def list_prompt_gate_runs(self, workspace_id: str = "default", limit: int = 20) -> Dict[str, Any]:
        return self._client._req(
            "GET", "/v1/platform/studio/prompt-gate/runs", params=_studio_prompt_gate_list_params(workspace_id, limit)
        )
