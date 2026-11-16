"""
Keelway Client SDK — Phase 19 Semantic Prompt Cache, Shadow Dual-Run Router
& QLoRA Distillation Flywheel Mixins (`client.platform`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient

_DEFAULT_SHADOW_PROMPT = "Refactor retry loop with bounded exponential backoff in Python"
_DEFAULT_SHADOW_RESPONSE = (
    "def retry_with_backoff(max_attempts: int = 3, base_delay: float = 0.25) -> float: "
    "return min(4.0, base_delay * (2 ** max_attempts))"
)
_VALID_EXPORT_FORMATS = ("sft_jsonl", "dpo_preference")


def _clean_non_empty(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return clean


def _clean_ws(workspace_id: str) -> str:
    return str(workspace_id or "default").strip() or "default"


def _validate_unit_score(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not (0.0 <= float(value) <= 1.0):
        raise ValueError(f"{field_name} must be between 0.0 and 1.0.")
    return float(value)


def _validate_positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or int(value) < 1:
        raise ValueError(f"{field_name} must be >= 1.")
    return int(value)


def _shadow_evaluate_body(
    prompt: str, workspace_id: str, task_tag: str, frontier_model: str, local_model: str,
    frontier_response: str, local_response: str, frontier_cost_usd: float,
    frontier_latency_ms: int, local_latency_ms: int, similarity_threshold: float, bypass_cache: bool,
) -> Dict[str, Any]:
    if isinstance(frontier_cost_usd, bool) or float(frontier_cost_usd) < 0.0:
        raise ValueError("frontier_cost_usd must be >= 0.0.")
    if isinstance(frontier_latency_ms, bool) or int(frontier_latency_ms) < 0:
        raise ValueError("frontier_latency_ms must be >= 0.")
    if isinstance(local_latency_ms, bool) or int(local_latency_ms) < 0:
        raise ValueError("local_latency_ms must be >= 0.")
    return {
        "workspace_id": _clean_ws(workspace_id),
        "task_tag": _clean_non_empty(task_tag, "task_tag"),
        "prompt": _clean_non_empty(prompt, "prompt"),
        "frontier_model": _clean_non_empty(frontier_model, "frontier_model"),
        "local_model": _clean_non_empty(local_model, "local_model"),
        "frontier_response": _clean_non_empty(frontier_response, "frontier_response"),
        "local_response": _clean_non_empty(local_response, "local_response"),
        "frontier_cost_usd": float(frontier_cost_usd),
        "frontier_latency_ms": int(frontier_latency_ms),
        "local_latency_ms": int(local_latency_ms),
        "similarity_threshold": _validate_unit_score(similarity_threshold, "similarity_threshold"),
        "bypass_cache": bool(bypass_cache),
    }


def _shadow_pairs_params(workspace_id: str, task_tag: Optional[str], limit: int) -> Dict[str, Any]:
    params: Dict[str, Any] = {"workspace_id": _clean_ws(workspace_id), "limit": _validate_positive_int(limit, "limit")}
    if task_tag is not None and str(task_tag).strip():
        params["task_tag"] = str(task_tag).strip()
    return params


def _compile_dataset_body(
    workspace_id: str, task_tag: str, export_format: str, target_base_model: str, min_parity_score: float,
) -> Dict[str, Any]:
    clean_format = str(export_format or "").strip()
    if clean_format not in _VALID_EXPORT_FORMATS:
        raise ValueError(f"export_format must be one of {list(_VALID_EXPORT_FORMATS)}.")
    return {
        "workspace_id": _clean_ws(workspace_id),
        "task_tag": str(task_tag or "").strip(),
        "export_format": clean_format,
        "target_base_model": _clean_non_empty(target_base_model, "target_base_model"),
        "min_parity_score": _validate_unit_score(min_parity_score, "min_parity_score"),
    }


def _promotion_evaluate_body(
    workspace_id: str, task_tag: str, target_local_model: str,
    min_pairs: int, min_avg_parity: float, monthly_request_volume: int,
) -> Dict[str, Any]:
    return {
        "workspace_id": _clean_ws(workspace_id),
        "task_tag": _clean_non_empty(task_tag, "task_tag"),
        "target_local_model": _clean_non_empty(target_local_model, "target_local_model"),
        "min_pairs": _validate_positive_int(min_pairs, "min_pairs"),
        "min_avg_parity": _validate_unit_score(min_avg_parity, "min_avg_parity"),
        "monthly_request_volume": _validate_positive_int(monthly_request_volume, "monthly_request_volume"),
    }


class AsyncPlatformDistillMixin:
    """Asynchronous Phase 19 Semantic Prompt Cache & QLoRA Distillation methods."""

    _client: "AsyncKeelwayClient"

    async def evaluate_shadow_prompt(
        self, prompt: str = _DEFAULT_SHADOW_PROMPT, *, workspace_id: str = "default", task_tag: str = "code-patch",
        frontier_model: str = "claude-3-7-sonnet", local_model: str = "keelway-core:7b",
        frontier_response: str = _DEFAULT_SHADOW_RESPONSE, local_response: str = _DEFAULT_SHADOW_RESPONSE,
        frontier_cost_usd: float = 0.018, frontier_latency_ms: int = 840, local_latency_ms: int = 95,
        similarity_threshold: float = 0.82, bypass_cache: bool = False,
    ) -> Dict[str, Any]:
        body = _shadow_evaluate_body(
            prompt, workspace_id, task_tag, frontier_model, local_model, frontier_response,
            local_response, frontier_cost_usd, frontier_latency_ms, local_latency_ms, similarity_threshold, bypass_cache,
        )
        return await self._client._req("POST", "/v1/platform/distill/shadow/evaluate", json=body)

    async def list_shadow_pairs(
        self, workspace_id: str = "default", task_tag: Optional[str] = None, limit: int = 25,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET", "/v1/platform/distill/shadow/pairs", params=_shadow_pairs_params(workspace_id, task_tag, limit)
        )

    async def get_semantic_cache_stats(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/distill/cache/stats", params={"workspace_id": _clean_ws(workspace_id)})

    async def compile_distillation_dataset(
        self, *, workspace_id: str = "default", task_tag: str = "", export_format: str = "dpo_preference",
        target_base_model: str = "keelway-core:7b", min_parity_score: float = 0.0,
    ) -> Dict[str, Any]:
        body = _compile_dataset_body(workspace_id, task_tag, export_format, target_base_model, min_parity_score)
        return await self._client._req("POST", "/v1/platform/distill/datasets/compile", json=body)

    async def list_distillation_datasets(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/distill/datasets", params=_shadow_pairs_params(workspace_id, None, limit))

    async def evaluate_distillation_promotion(
        self, *, workspace_id: str = "default", task_tag: str = "code-patch", target_local_model: str = "keelway-core:7b",
        min_pairs: int = 3, min_avg_parity: float = 0.85, monthly_request_volume: int = 50000,
    ) -> Dict[str, Any]:
        body = _promotion_evaluate_body(workspace_id, task_tag, target_local_model, min_pairs, min_avg_parity, monthly_request_volume)
        return await self._client._req("POST", "/v1/platform/distill/promotion/evaluate", json=body)


class SyncPlatformDistillMixin:
    """Synchronous Phase 19 Semantic Prompt Cache & QLoRA Distillation methods."""

    _client: "KeelwayClient"

    def evaluate_shadow_prompt(
        self, prompt: str = _DEFAULT_SHADOW_PROMPT, *, workspace_id: str = "default", task_tag: str = "code-patch",
        frontier_model: str = "claude-3-7-sonnet", local_model: str = "keelway-core:7b",
        frontier_response: str = _DEFAULT_SHADOW_RESPONSE, local_response: str = _DEFAULT_SHADOW_RESPONSE,
        frontier_cost_usd: float = 0.018, frontier_latency_ms: int = 840, local_latency_ms: int = 95,
        similarity_threshold: float = 0.82, bypass_cache: bool = False,
    ) -> Dict[str, Any]:
        body = _shadow_evaluate_body(
            prompt, workspace_id, task_tag, frontier_model, local_model, frontier_response,
            local_response, frontier_cost_usd, frontier_latency_ms, local_latency_ms, similarity_threshold, bypass_cache,
        )
        return self._client._req("POST", "/v1/platform/distill/shadow/evaluate", json=body)

    def list_shadow_pairs(
        self, workspace_id: str = "default", task_tag: Optional[str] = None, limit: int = 25,
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET", "/v1/platform/distill/shadow/pairs", params=_shadow_pairs_params(workspace_id, task_tag, limit)
        )

    def get_semantic_cache_stats(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/distill/cache/stats", params={"workspace_id": _clean_ws(workspace_id)})

    def compile_distillation_dataset(
        self, *, workspace_id: str = "default", task_tag: str = "", export_format: str = "dpo_preference",
        target_base_model: str = "keelway-core:7b", min_parity_score: float = 0.0,
    ) -> Dict[str, Any]:
        body = _compile_dataset_body(workspace_id, task_tag, export_format, target_base_model, min_parity_score)
        return self._client._req("POST", "/v1/platform/distill/datasets/compile", json=body)

    def list_distillation_datasets(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/distill/datasets", params=_shadow_pairs_params(workspace_id, None, limit))

    def evaluate_distillation_promotion(
        self, *, workspace_id: str = "default", task_tag: str = "code-patch", target_local_model: str = "keelway-core:7b",
        min_pairs: int = 3, min_avg_parity: float = 0.85, monthly_request_volume: int = 50000,
    ) -> Dict[str, Any]:
        body = _promotion_evaluate_body(workspace_id, task_tag, target_local_model, min_pairs, min_avg_parity, monthly_request_volume)
        return self._client._req("POST", "/v1/platform/distill/promotion/evaluate", json=body)


PlatformDistillMixin = SyncPlatformDistillMixin
