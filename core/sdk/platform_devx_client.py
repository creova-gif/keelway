"""
Keelway Client SDK — Phase 11 OpenTelemetry GenAI Flight-Tape Time-Travel,
Trace-to-Eval Promotion & LangGraph Static AST Migration Mixins (`client.platform`).

Defines `AsyncPlatformDevxMixin` and `SyncPlatformDevxMixin` inherited by
`AsyncPlatformRuntimeMixin` and `SyncPlatformRuntimeMixin` for 100% sync + async parity across
`/v1/platform/traces/*`, `/v1/platform/eval/dataset*`, and `/v1/platform/migrate/langgraph`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import quote

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient


def _devx_seg(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return quote(clean, safe="")


def _devx_ingest_traces_body(
    spans: Optional[List[Dict[str, Any]]],
    workspace_id: str,
    workflow_name: str,
    source_framework: str,
    resource_spans: Optional[List[Dict[str, Any]]],
    trace_id: Optional[str],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "workflow_name": workflow_name,
        "source_framework": source_framework,
    }
    if spans is not None:
        body["spans"] = list(spans)
    if resource_spans is not None:
        normalized_rs = list(resource_spans)
        body["resourceSpans"] = normalized_rs
        body["resource_spans"] = normalized_rs
    if trace_id is not None:
        clean_tid = str(trace_id).strip()
        if clean_tid:
            body["trace_id"] = clean_tid
    return body


def _devx_replay_body(
    workspace_id: str,
    from_step_index: int,
    override_prompt: Optional[str],
    override_model: Optional[str],
    override_state: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if int(from_step_index) < 0:
        raise ValueError("from_step_index must be >= 0.")
    body: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "from_step_index": int(from_step_index),
    }
    if override_prompt is not None:
        body["override_prompt"] = override_prompt
    if override_model is not None:
        body["override_model"] = override_model
    if override_state is not None:
        body["override_state"] = dict(override_state)
    return body


def _devx_promote_eval_body(
    trace_id: str,
    workspace_id: str,
    title: Optional[str],
    expected_substrings: Optional[List[str]],
    forbidden_substrings: Optional[List[str]],
) -> Dict[str, Any]:
    clean_tid = str(trace_id or "").strip()
    if not clean_tid:
        raise ValueError("trace_id must be non-empty.")
    body: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "trace_id": clean_tid,
    }
    if title is not None:
        body["title"] = title
    if expected_substrings is not None:
        body["expected_substrings"] = list(expected_substrings)
    if forbidden_substrings is not None:
        body["forbidden_substrings"] = list(forbidden_substrings)
    return body


def _devx_migrate_langgraph_body(
    source_code: str,
    workspace_id: str,
    source_language: str,
    workflow_name: Optional[str],
) -> Dict[str, Any]:
    if not str(source_code or "").strip():
        raise ValueError("source_code must be non-empty.")
    body: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "source_code": source_code,
        "source_language": source_language,
    }
    if workflow_name is not None:
        body["workflow_name"] = workflow_name
    return body


class AsyncPlatformDevxMixin:
    """Asynchronous Phase 11 Flight-Tape Time-Travel, Trace-to-Eval & LangGraph Importer methods."""

    _client: "AsyncKeelwayClient"

    async def ingest_otel_traces(
        self,
        spans: Optional[List[Dict[str, Any]]] = None,
        *,
        workspace_id: str = "default",
        workflow_name: str = "agent-trace",
        source_framework: str = "opentelemetry_genai",
        resource_spans: Optional[List[Dict[str, Any]]] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/traces/ingest",
            json=_devx_ingest_traces_body(
                spans,
                workspace_id,
                workflow_name,
                source_framework,
                resource_spans,
                trace_id,
            ),
        )

    async def list_flight_tapes(
        self,
        *,
        workspace_id: str = "default",
        limit: int = 20,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/platform/traces",
            params={"workspace_id": workspace_id, "limit": int(limit)},
        )

    async def replay_flight_tape(
        self,
        trace_id: str,
        *,
        workspace_id: str = "default",
        from_step_index: int = 0,
        override_prompt: Optional[str] = None,
        override_model: Optional[str] = None,
        override_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            f"/v1/platform/traces/{_devx_seg(trace_id, 'trace_id')}/replay",
            json=_devx_replay_body(
                workspace_id,
                from_step_index,
                override_prompt,
                override_model,
                override_state,
            ),
        )

    async def promote_trace_to_eval(
        self,
        trace_id: str,
        *,
        workspace_id: str = "default",
        title: Optional[str] = None,
        expected_substrings: Optional[List[str]] = None,
        forbidden_substrings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/eval/dataset/promote",
            json=_devx_promote_eval_body(
                trace_id,
                workspace_id,
                title,
                expected_substrings,
                forbidden_substrings,
            ),
        )

    async def list_eval_dataset_cases(
        self,
        *,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/platform/eval/dataset",
            params={"workspace_id": workspace_id},
        )

    async def migrate_langgraph_source(
        self,
        source_code: str,
        *,
        workspace_id: str = "default",
        source_language: str = "python",
        workflow_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/migrate/langgraph",
            json=_devx_migrate_langgraph_body(
                source_code,
                workspace_id,
                source_language,
                workflow_name,
            ),
        )


class SyncPlatformDevxMixin:
    """Synchronous Phase 11 Flight-Tape Time-Travel, Trace-to-Eval & LangGraph Importer methods."""

    _client: "KeelwayClient"

    def ingest_otel_traces(
        self,
        spans: Optional[List[Dict[str, Any]]] = None,
        *,
        workspace_id: str = "default",
        workflow_name: str = "agent-trace",
        source_framework: str = "opentelemetry_genai",
        resource_spans: Optional[List[Dict[str, Any]]] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/traces/ingest",
            json=_devx_ingest_traces_body(
                spans,
                workspace_id,
                workflow_name,
                source_framework,
                resource_spans,
                trace_id,
            ),
        )

    def list_flight_tapes(
        self,
        *,
        workspace_id: str = "default",
        limit: int = 20,
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/platform/traces",
            params={"workspace_id": workspace_id, "limit": int(limit)},
        )

    def replay_flight_tape(
        self,
        trace_id: str,
        *,
        workspace_id: str = "default",
        from_step_index: int = 0,
        override_prompt: Optional[str] = None,
        override_model: Optional[str] = None,
        override_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            f"/v1/platform/traces/{_devx_seg(trace_id, 'trace_id')}/replay",
            json=_devx_replay_body(
                workspace_id,
                from_step_index,
                override_prompt,
                override_model,
                override_state,
            ),
        )

    def promote_trace_to_eval(
        self,
        trace_id: str,
        *,
        workspace_id: str = "default",
        title: Optional[str] = None,
        expected_substrings: Optional[List[str]] = None,
        forbidden_substrings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/eval/dataset/promote",
            json=_devx_promote_eval_body(
                trace_id,
                workspace_id,
                title,
                expected_substrings,
                forbidden_substrings,
            ),
        )

    def list_eval_dataset_cases(
        self,
        *,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/platform/eval/dataset",
            params={"workspace_id": workspace_id},
        )

    def migrate_langgraph_source(
        self,
        source_code: str,
        *,
        workspace_id: str = "default",
        source_language: str = "python",
        workflow_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/migrate/langgraph",
            json=_devx_migrate_langgraph_body(
                source_code,
                workspace_id,
                source_language,
                workflow_name,
            ),
        )
