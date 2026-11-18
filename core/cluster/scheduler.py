"""
Multi-Node GPU Cluster Scheduler (`KEEL-CLUSTER-008`).

Provides sovereign GPU worker registration (`ollama_metal`, `vllm`, `ray_serve`),
node drain/restore lifecycle, heartbeat telemetry, and deterministic fail-closed
model placement across regional and air-gap residency boundaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import threading
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

VALID_RUNTIMES = frozenset({"ollama_metal", "vllm", "ray_serve"})
VALID_NODE_REGIONS = frozenset({"airgap_local", "us", "eu", "africa"})
VALID_RESIDENCY_ZONES = frozenset({"global", "airgap_local", "us", "eu", "africa"})
VALID_PRIVACY_LEVELS = frozenset({"standard", "public", "private", "air_gap"})
PRIVATE_PRIVACY_LEVELS = frozenset({"private", "air_gap"})

ClusterRuntime = Literal["ollama_metal", "vllm", "ray_serve"]
ClusterRegion = Literal["airgap_local", "us", "eu", "africa"]
NodeStatus = Literal["healthy", "drained", "unhealthy"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utilization_pct(total_vram_gb: float, free_vram_gb: float) -> float:
    if total_vram_gb <= 0:
        return 100.0
    used = max(0.0, total_vram_gb - free_vram_gb)
    return round(min(100.0, (used / total_vram_gb) * 100.0), 2)


class ClusterNodeNotFoundError(ValueError):
    """Raised when referencing an unregistered cluster worker node."""


class PlacementValidationError(ValueError):
    """Raised when placement constraints contain unsupported residency, privacy, or resource parameters."""


class PlacementCapacityError(ValueError):
    """Raised when no healthy non-drained node satisfies residency, privacy, VRAM, or TP constraints."""


class _SubscriptableModel(BaseModel):
    """Pydantic model supporting both typed attribute access and read-only dict-key lookup."""

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and hasattr(self, key)


class ClusterNode(_SubscriptableModel):
    """Registered GPU inference worker node in the Keelway cluster fleet."""

    node_id: str = Field(..., min_length=1, max_length=128)
    runtime: ClusterRuntime
    region: ClusterRegion
    gpu_model: str = Field(default="Generic Accelerator", min_length=1, max_length=128)
    gpu_count: int = Field(default=1, ge=1)
    total_vram_gb: float = Field(..., gt=0.0)
    free_vram_gb: float = Field(..., ge=0.0)
    utilization_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    active_requests: int = Field(default=0, ge=0)
    status: NodeStatus = "healthy"
    loaded_models: List[str] = Field(default_factory=list)
    last_heartbeat_at: str


class PlacementDecision(_SubscriptableModel):
    """Deterministic placement decision and cryptographic SHA-256 scheduling receipt."""

    selected_node_id: str
    model_id: str
    runtime: ClusterRuntime
    region: ClusterRegion
    privacy_level: str
    region_residency: str
    required_vram_gb: float
    tensor_parallel: int
    estimated_queue_ms: float
    score: float
    candidates_evaluated: int
    receipt_sha256: str
    decided_at: str


DEFAULT_CLUSTER_NODES: List[Dict[str, Any]] = [
    {
        "node_id": "node-metal-local-01",
        "runtime": "ollama_metal",
        "region": "airgap_local",
        "gpu_model": "Apple M-Series Metal Unified",
        "gpu_count": 1,
        "total_vram_gb": 32.0,
        "free_vram_gb": 32.0,
        "active_requests": 0,
        "loaded_models": ["keelway-core:7b", "qwen2.5-coder:7b"],
    },
    {
        "node_id": "node-vllm-us-01",
        "runtime": "vllm",
        "region": "us",
        "gpu_model": "NVIDIA H100 80GB",
        "gpu_count": 2,
        "total_vram_gb": 160.0,
        "free_vram_gb": 160.0,
        "active_requests": 1,
        "loaded_models": ["keelway-coder:14b-v2", "deepseek-r1:70b"],
    },
    {
        "node_id": "node-vllm-eu-01",
        "runtime": "vllm",
        "region": "eu",
        "gpu_model": "NVIDIA A100 80GB",
        "gpu_count": 1,
        "total_vram_gb": 80.0,
        "free_vram_gb": 80.0,
        "active_requests": 0,
        "loaded_models": ["qwen2.5-coder:7b"],
    },
    {
        "node_id": "node-ray-af-01",
        "runtime": "ray_serve",
        "region": "africa",
        "gpu_model": "NVIDIA L40S 48GB",
        "gpu_count": 1,
        "total_vram_gb": 48.0,
        "free_vram_gb": 48.0,
        "active_requests": 0,
        "loaded_models": ["keelway-core:7b"],
    },
]


class ClusterScheduler:
    """Thread-safe multi-node GPU cluster scheduler with fail-closed residency & privacy routing."""

    def __init__(self, seed_defaults: bool = True) -> None:
        self._lock = threading.RLock()
        self._nodes: Dict[str, ClusterNode] = {}
        if seed_defaults:
            for spec in DEFAULT_CLUSTER_NODES:
                self.register_node(**spec)

    def list_nodes(
        self,
        region: Optional[str] = None,
        runtime: Optional[str] = None,
        include_drained: bool = True,
    ) -> List[ClusterNode]:
        """List registered worker nodes filtered by region, runtime, and drain state."""
        with self._lock:
            nodes = list(self._nodes.values())
        if region is not None:
            nodes = [n for n in nodes if n.region == region]
        if runtime is not None:
            nodes = [n for n in nodes if n.runtime == runtime]
        if not include_drained:
            nodes = [n for n in nodes if n.status != "drained"]
        return [n.model_copy(deep=True) for n in nodes]

    def get_node(self, node_id: str) -> ClusterNode:
        """Return a copy of a single registered worker node or raise ClusterNodeNotFoundError."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                raise ClusterNodeNotFoundError(f"Cluster node '{node_id}' is not registered.")
            return node.model_copy(deep=True)

    def register_node(
        self,
        node_id: str,
        runtime: str,
        region: str,
        total_vram_gb: float,
        free_vram_gb: Optional[float] = None,
        gpu_count: int = 1,
        gpu_model: str = "Generic Accelerator",
        loaded_models: Optional[List[str]] = None,
        active_requests: int = 0,
        status: NodeStatus = "healthy",
    ) -> ClusterNode:
        """Register or update a GPU worker node after validating runtime, region, and VRAM bounds."""
        clean_id = node_id.strip()
        if not clean_id:
            raise PlacementValidationError("node_id must be a non-empty string.")
        if runtime not in VALID_RUNTIMES:
            raise PlacementValidationError(
                f"Unsupported runtime '{runtime}'. Must be one of {sorted(VALID_RUNTIMES)}."
            )
        if region not in VALID_NODE_REGIONS:
            raise PlacementValidationError(
                f"Unsupported node region '{region}'. Must be one of {sorted(VALID_NODE_REGIONS)}."
            )
        if total_vram_gb <= 0:
            raise PlacementValidationError("total_vram_gb must be greater than 0.")
        if gpu_count < 1:
            raise PlacementValidationError("gpu_count must be at least 1.")
        if active_requests < 0:
            raise PlacementValidationError("active_requests must be non-negative.")

        effective_free = float(total_vram_gb if free_vram_gb is None else free_vram_gb)
        if effective_free < 0 or effective_free > total_vram_gb:
            raise PlacementValidationError(
                f"free_vram_gb ({effective_free}) must be between 0 and total_vram_gb ({total_vram_gb})."
            )

        node = ClusterNode(
            node_id=clean_id,
            runtime=runtime,  # type: ignore[arg-type]
            region=region,  # type: ignore[arg-type]
            gpu_model=gpu_model.strip() or "Generic Accelerator",
            gpu_count=gpu_count,
            total_vram_gb=round(float(total_vram_gb), 2),
            free_vram_gb=round(effective_free, 2),
            utilization_pct=_utilization_pct(float(total_vram_gb), effective_free),
            active_requests=active_requests,
            status=status,
            loaded_models=list(loaded_models or []),
            last_heartbeat_at=_utc_now_iso(),
        )
        with self._lock:
            self._nodes[clean_id] = node
            return node.model_copy(deep=True)

    def drain_node(self, node_id: str) -> ClusterNode:
        """Mark a worker node as drained so new placements bypass it."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                raise ClusterNodeNotFoundError(f"Cluster node '{node_id}' is not registered.")
            updated = node.model_copy(
                update={"status": "drained", "last_heartbeat_at": _utc_now_iso()},
                deep=True,
            )
            self._nodes[node_id] = updated
            return updated.model_copy(deep=True)

    def restore_node(self, node_id: str) -> ClusterNode:
        """Restore a drained or unhealthy worker node back to healthy scheduling eligibility."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                raise ClusterNodeNotFoundError(f"Cluster node '{node_id}' is not registered.")
            updated = node.model_copy(
                update={"status": "healthy", "last_heartbeat_at": _utc_now_iso()},
                deep=True,
            )
            self._nodes[node_id] = updated
            return updated.model_copy(deep=True)

    def heartbeat_node(
        self,
        node_id: str,
        active_requests: int,
        free_vram_gb: float,
    ) -> ClusterNode:
        """Update live queue depth and free VRAM telemetry for a registered worker node."""
        if active_requests < 0:
            raise PlacementValidationError("active_requests must be non-negative.")
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                raise ClusterNodeNotFoundError(f"Cluster node '{node_id}' is not registered.")
            if free_vram_gb < 0 or free_vram_gb > node.total_vram_gb:
                raise PlacementValidationError(
                    f"free_vram_gb ({free_vram_gb}) must be between 0 and total_vram_gb ({node.total_vram_gb})."
                )
            eff_free = round(float(free_vram_gb), 2)
            updated = node.model_copy(
                update={
                    "active_requests": int(active_requests),
                    "free_vram_gb": eff_free,
                    "utilization_pct": _utilization_pct(node.total_vram_gb, eff_free),
                    "last_heartbeat_at": _utc_now_iso(),
                },
                deep=True,
            )
            self._nodes[node_id] = updated
            return updated.model_copy(deep=True)

    def schedule_placement(
        self,
        model_id: str,
        required_vram_gb: float,
        region_residency: str = "global",
        privacy_level: str = "standard",
        runtime_preference: Optional[str] = None,
        tensor_parallel: int = 1,
    ) -> PlacementDecision:
        """
        Deterministically select an eligible worker node enforcing fail-closed residency & privacy.

        Raises ValueError (PlacementValidationError or PlacementCapacityError) when constraints
        are invalid or cannot be satisfied by any healthy non-drained worker node.
        """
        clean_model = model_id.strip()
        if not clean_model:
            raise PlacementValidationError("model_id must be a non-empty string.")
        if required_vram_gb <= 0:
            raise PlacementValidationError("required_vram_gb must be greater than 0.")
        if tensor_parallel < 1:
            raise PlacementValidationError("tensor_parallel must be at least 1.")
        if region_residency not in VALID_RESIDENCY_ZONES:
            raise PlacementValidationError(
                f"Unsupported region_residency '{region_residency}'. Must be one of {sorted(VALID_RESIDENCY_ZONES)}."
            )
        if privacy_level not in VALID_PRIVACY_LEVELS:
            raise PlacementValidationError(
                f"Unsupported privacy_level '{privacy_level}'. Must be one of {sorted(VALID_PRIVACY_LEVELS)}."
            )
        if runtime_preference is not None and runtime_preference not in VALID_RUNTIMES:
            raise PlacementValidationError(
                f"Unsupported runtime_preference '{runtime_preference}'. Must be one of {sorted(VALID_RUNTIMES)}."
            )

        require_airgap = privacy_level in PRIVATE_PRIVACY_LEVELS or region_residency == "airgap_local"
        if require_airgap and region_residency not in ("global", "airgap_local"):
            raise PlacementCapacityError(
                f"Fail-closed residency conflict: privacy_level='{privacy_level}' requires 'airgap_local' "
                f"and cannot route to region_residency='{region_residency}'."
            )

        with self._lock:
            snapshot = list(self._nodes.values())

        eligible: List[ClusterNode] = []
        for node in snapshot:
            if node.status != "healthy":
                continue
            if require_airgap and node.region != "airgap_local":
                continue
            if not require_airgap and region_residency != "global" and node.region != region_residency:
                continue
            if node.free_vram_gb < required_vram_gb:
                continue
            if node.gpu_count < tensor_parallel:
                continue
            eligible.append(node)

        if not eligible:
            target_zone = "airgap_local" if require_airgap else region_residency
            raise PlacementCapacityError(
                f"No healthy non-drained cluster node satisfies model='{clean_model}', "
                f"zone='{target_zone}', privacy='{privacy_level}', "
                f"required_vram_gb={required_vram_gb}, tensor_parallel={tensor_parallel}."
            )

        def _rank_key(node: ClusterNode) -> tuple[float, str]:
            used_ratio = (node.total_vram_gb - node.free_vram_gb) / node.total_vram_gb
            runtime_penalty = (
                0.0 if (runtime_preference is None or node.runtime == runtime_preference) else 45.0
            )
            queue_penalty = float(node.active_requests) * 15.0
            util_penalty = used_ratio * 30.0
            warm_bonus = -3.0 if clean_model in node.loaded_models else 0.0
            total_penalty = round(runtime_penalty + queue_penalty + util_penalty + warm_bonus, 6)
            return (total_penalty, node.node_id)

        ranked = sorted(eligible, key=_rank_key)
        winner = ranked[0]
        winner_penalty, _ = _rank_key(winner)
        score = round(max(0.0, min(100.0, 100.0 - winner_penalty)), 2)
        warm_dispatch_ms = 4.0 if clean_model in winner.loaded_models else 16.0
        estimated_queue_ms = round(winner.active_requests * 25.0 + warm_dispatch_ms, 2)

        receipt_payload = {
            "estimated_queue_ms": estimated_queue_ms,
            "model_id": clean_model,
            "privacy_level": privacy_level,
            "region": winner.region,
            "region_residency": region_residency,
            "required_vram_gb": round(float(required_vram_gb), 2),
            "runtime": winner.runtime,
            "selected_node_id": winner.node_id,
            "tensor_parallel": int(tensor_parallel),
        }
        canonical = json.dumps(receipt_payload, sort_keys=True, separators=(",", ":"))
        receipt_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return PlacementDecision(
            selected_node_id=winner.node_id,
            model_id=clean_model,
            runtime=winner.runtime,
            region=winner.region,
            privacy_level=privacy_level,
            region_residency=region_residency,
            required_vram_gb=round(float(required_vram_gb), 2),
            tensor_parallel=int(tensor_parallel),
            estimated_queue_ms=estimated_queue_ms,
            score=score,
            candidates_evaluated=len(eligible),
            receipt_sha256=receipt_sha256,
            decided_at=_utc_now_iso(),
        )


cluster_scheduler = ClusterScheduler()
