"""
Keelway Client SDK — Phase 16 Typed Structured-Output & Content-Block Normalizer
+ Autonomous Self-Healing Failure Root-Causer Mixins (`client.platform`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Union
from urllib.parse import quote

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient

_VALID_PROVIDER_FORMATS = ("deepseek_opencore", "openai", "anthropic", "gemini")


def _healing_seg(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return quote(clean, safe="")


def _normalize_blocks_body(
    raw_payload: Union[Dict[str, Any], str], provider_format: str, model_id: str, workspace_id: str
) -> Dict[str, Any]:
    clean_fmt = str(provider_format or "").strip()
    if clean_fmt not in _VALID_PROVIDER_FORMATS:
        raise ValueError(f"provider_format must be one of {list(_VALID_PROVIDER_FORMATS)}.")
    clean_model = str(model_id or "").strip()
    if not clean_model:
        raise ValueError("model_id must be non-empty.")
    if not isinstance(raw_payload, (dict, str)):
        raise ValueError("raw_payload must be a dict or str.")
    return {
        "workspace_id": workspace_id,
        "provider_format": clean_fmt,
        "model_id": clean_model,
        "raw_payload": dict(raw_payload) if isinstance(raw_payload, dict) else raw_payload,
    }


def _enforce_structured_body(
    json_schema: Optional[Dict[str, Any]],
    raw_output: Union[str, Dict[str, Any]],
    workspace_id: str,
    schema_name: str,
    provider_format: str,
    model_id: str,
    strict_mode: bool,
    fail_closed: bool,
) -> Dict[str, Any]:
    if json_schema is None or not isinstance(json_schema, dict):
        raise ValueError("json_schema must be a dict.")
    clean_schema = str(schema_name or "").strip()
    if not clean_schema:
        raise ValueError("schema_name must be non-empty.")
    clean_fmt = str(provider_format or "").strip()
    if clean_fmt not in _VALID_PROVIDER_FORMATS:
        raise ValueError(f"provider_format must be one of {list(_VALID_PROVIDER_FORMATS)}.")
    clean_model = str(model_id or "").strip()
    if not clean_model:
        raise ValueError("model_id must be non-empty.")
    if not isinstance(raw_output, (str, dict)):
        raise ValueError("raw_output must be a str or dict.")
    return {
        "workspace_id": workspace_id,
        "schema_name": clean_schema,
        "provider_format": clean_fmt,
        "model_id": clean_model,
        "json_schema": dict(json_schema),
        "raw_output": dict(raw_output) if isinstance(raw_output, dict) else raw_output,
        "strict_mode": bool(strict_mode),
        "fail_closed": bool(fail_closed),
    }


def _healing_list_params(workspace_id: str, limit: int) -> Dict[str, Any]:
    if isinstance(limit, bool) or int(limit) < 1:
        raise ValueError("limit must be >= 1.")
    return {"workspace_id": workspace_id, "limit": int(limit)}


def _diagnose_root_cause_body(
    workspace_id: str, trace_id: Optional[str], workflow_name: str, failed_step: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    clean_wf = str(workflow_name or "").strip()
    if not clean_wf:
        raise ValueError("workflow_name must be non-empty.")
    body: Dict[str, Any] = {"workspace_id": workspace_id, "workflow_name": clean_wf}
    if trace_id is not None and str(trace_id).strip():
        body["trace_id"] = str(trace_id).strip()
    if failed_step is not None:
        if not isinstance(failed_step, dict):
            raise ValueError("failed_step must be a dict.")
        body["failed_step"] = dict(failed_step)
    return body


def _apply_patch_body(workspace_id: str, promote_to_eval: bool, eval_title: Optional[str]) -> Dict[str, Any]:
    body: Dict[str, Any] = {"workspace_id": workspace_id, "promote_to_eval": bool(promote_to_eval)}
    if eval_title is not None and str(eval_title).strip():
        body["eval_title"] = str(eval_title).strip()
    return body


class AsyncPlatformHealingMixin:
    """Asynchronous Phase 16 Structured-Output & Self-Healing Root-Causer methods."""

    _client: "AsyncKeelwayClient"

    async def normalize_content_blocks(
        self,
        raw_payload: Union[Dict[str, Any], str] = "",
        *,
        provider_format: str = "deepseek_opencore",
        model_id: str = "keelway-core:7b",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        body = _normalize_blocks_body(raw_payload, provider_format, model_id, workspace_id)
        return await self._client._req("POST", "/v1/platform/healing/content-blocks/normalize", json=body)

    async def enforce_structured_output(
        self,
        json_schema: Optional[Dict[str, Any]] = None,
        raw_output: Union[str, Dict[str, Any]] = "",
        *,
        workspace_id: str = "default",
        schema_name: str = "AgentDecisionContract",
        provider_format: str = "deepseek_opencore",
        model_id: str = "keelway-core:7b",
        strict_mode: bool = False,
        fail_closed: bool = True,
    ) -> Dict[str, Any]:
        body = _enforce_structured_body(
            json_schema, raw_output, workspace_id, schema_name, provider_format, model_id, strict_mode, fail_closed
        )
        return await self._client._req("POST", "/v1/platform/healing/structured/enforce", json=body)

    async def list_structured_output_runs(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/healing/structured/runs", params=_healing_list_params(workspace_id, limit))

    async def diagnose_failure_root_cause(
        self,
        *,
        workspace_id: str = "default",
        trace_id: Optional[str] = None,
        workflow_name: str = "invoice-triage-agent",
        failed_step: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = _diagnose_root_cause_body(workspace_id, trace_id, workflow_name, failed_step)
        return await self._client._req("POST", "/v1/platform/healing/root-cause/diagnose", json=body)

    async def apply_self_healing_patch(
        self,
        diagnosis_id: str,
        *,
        workspace_id: str = "default",
        promote_to_eval: bool = True,
        eval_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        seg = _healing_seg(diagnosis_id, "diagnosis_id")
        return await self._client._req("POST", f"/v1/platform/healing/root-cause/{seg}/apply", json=_apply_patch_body(workspace_id, promote_to_eval, eval_title))

    async def list_self_healing_diagnoses(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/healing/root-cause/diagnoses", params=_healing_list_params(workspace_id, limit))


class SyncPlatformHealingMixin:
    """Synchronous Phase 16 Structured-Output & Self-Healing Root-Causer methods."""

    _client: "KeelwayClient"

    def normalize_content_blocks(
        self,
        raw_payload: Union[Dict[str, Any], str] = "",
        *,
        provider_format: str = "deepseek_opencore",
        model_id: str = "keelway-core:7b",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        body = _normalize_blocks_body(raw_payload, provider_format, model_id, workspace_id)
        return self._client._req("POST", "/v1/platform/healing/content-blocks/normalize", json=body)

    def enforce_structured_output(
        self,
        json_schema: Optional[Dict[str, Any]] = None,
        raw_output: Union[str, Dict[str, Any]] = "",
        *,
        workspace_id: str = "default",
        schema_name: str = "AgentDecisionContract",
        provider_format: str = "deepseek_opencore",
        model_id: str = "keelway-core:7b",
        strict_mode: bool = False,
        fail_closed: bool = True,
    ) -> Dict[str, Any]:
        body = _enforce_structured_body(
            json_schema, raw_output, workspace_id, schema_name, provider_format, model_id, strict_mode, fail_closed
        )
        return self._client._req("POST", "/v1/platform/healing/structured/enforce", json=body)

    def list_structured_output_runs(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/healing/structured/runs", params=_healing_list_params(workspace_id, limit))

    def diagnose_failure_root_cause(
        self,
        *,
        workspace_id: str = "default",
        trace_id: Optional[str] = None,
        workflow_name: str = "invoice-triage-agent",
        failed_step: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = _diagnose_root_cause_body(workspace_id, trace_id, workflow_name, failed_step)
        return self._client._req("POST", "/v1/platform/healing/root-cause/diagnose", json=body)

    def apply_self_healing_patch(
        self,
        diagnosis_id: str,
        *,
        workspace_id: str = "default",
        promote_to_eval: bool = True,
        eval_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        seg = _healing_seg(diagnosis_id, "diagnosis_id")
        return self._client._req("POST", f"/v1/platform/healing/root-cause/{seg}/apply", json=_apply_patch_body(workspace_id, promote_to_eval, eval_title))

    def list_self_healing_diagnoses(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/healing/root-cause/diagnoses", params=_healing_list_params(workspace_id, limit))


PlatformHealingMixin = SyncPlatformHealingMixin
