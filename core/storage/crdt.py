"""
Keelway Local-First Conflict-Free Replicated Data Type (CRDT) Subsystem.
Enables offline-first agent state tracking, Lamport timestamp ordering,
and conflict-free bidirectional delta synchronization for intermittent networks.
"""

import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class CRDTMutation:
    entity_id: str
    attribute: str
    value: Any
    lamport_clock: int
    actor_id: str
    timestamp_utc: float = field(default_factory=time.time)

    def hash(self) -> str:
        raw = f"{self.entity_id}:{self.attribute}:{self.value}:{self.lamport_clock}:{self.actor_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class LocalFirstSyncEngine:
    """Manages local state registers using Last-Write-Wins (LWW) CRDT resolution."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.lamport_clock = 0
        self.state_register: Dict[str, Dict[str, Tuple[Any, int, float, str]]] = {}
        self.mutation_log: List[CRDTMutation] = []

    def set_value(self, entity_id: str, attribute: str, value: Any) -> CRDTMutation:
        """Records a local state change and increments the Lamport clock."""
        self.lamport_clock += 1
        now = time.time()
        mutation = CRDTMutation(
            entity_id=entity_id,
            attribute=attribute,
            value=value,
            lamport_clock=self.lamport_clock,
            actor_id=self.node_id,
            timestamp_utc=now,
        )
        self.mutation_log.append(mutation)

        if entity_id not in self.state_register:
            self.state_register[entity_id] = {}

        self.state_register[entity_id][attribute] = (value, self.lamport_clock, now, self.node_id)
        return mutation

    def get_value(self, entity_id: str, attribute: str) -> Optional[Any]:
        if entity_id in self.state_register and attribute in self.state_register[entity_id]:
            return self.state_register[entity_id][attribute][0]
        return None

    def merge_remote_mutation(self, mutation: CRDTMutation) -> bool:
        """
        Merges a remote mutation using deterministic Last-Write-Wins (LWW) rules:
        Higher Lamport clock wins; ties broken deterministically by actor_id.
        """
        # Advance local clock
        self.lamport_clock = max(self.lamport_clock, mutation.lamport_clock) + 1

        entity_id = mutation.entity_id
        attr = mutation.attribute

        if entity_id not in self.state_register:
            self.state_register[entity_id] = {}

        if attr not in self.state_register[entity_id]:
            self.state_register[entity_id][attr] = (
                mutation.value,
                mutation.lamport_clock,
                mutation.timestamp_utc,
                mutation.actor_id,
            )
            return True

        curr_val, curr_clock, curr_time, curr_actor = self.state_register[entity_id][attr]

        # Determine winner: Lamport clock > Timestamp > Actor ID
        should_overwrite = False
        if mutation.lamport_clock > curr_clock:
            should_overwrite = True
        elif mutation.lamport_clock == curr_clock:
            if mutation.timestamp_utc > curr_time:
                should_overwrite = True
            elif mutation.timestamp_utc == curr_time:
                should_overwrite = mutation.actor_id > curr_actor

        if should_overwrite:
            self.state_register[entity_id][attr] = (
                mutation.value,
                mutation.lamport_clock,
                mutation.timestamp_utc,
                mutation.actor_id,
            )
            return True

        return False

    def export_delta(self, since_clock: int = 0) -> List[Dict[str, Any]]:
        """Exports mutations that occurred after a specific clock state."""
        return [
            {
                "entity_id": m.entity_id,
                "attribute": m.attribute,
                "value": m.value,
                "lamport_clock": m.lamport_clock,
                "actor_id": m.actor_id,
                "timestamp_utc": m.timestamp_utc,
            }
            for m in self.mutation_log
            if m.lamport_clock > since_clock
        ]
