"""
Enterprise Audit Merkle Tree & Cryptographic Inclusion Proof Engine.
Provides binary Merkle tree construction, audit hash chain verification,
and cryptographic inclusion proof generation & verification.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage.models import AuditEventRecord


def _node_hash(left: str, right: str) -> str:
    """Compute parent hash of two children: sha256((left + right).encode()).hexdigest()."""
    return hashlib.sha256((left + right).encode("utf-8")).hexdigest()


class AuditMerkleTree:
    """Binary Merkle Tree built over an audit event hash sequence."""

    def __init__(self, leaves: List[str]):
        self.leaves = list(leaves)
        self.levels: List[List[str]] = []
        self._build()

    def _build(self) -> None:
        if not self.leaves:
            return
        curr = list(self.leaves)
        self.levels.append(curr)
        while len(curr) > 1:
            # If odd number of nodes at any level, duplicate the last node
            if len(curr) % 2 != 0:
                curr.append(curr[-1])
            nxt: List[str] = []
            for i in range(0, len(curr), 2):
                nxt.append(_node_hash(curr[i], curr[i + 1]))
            curr = nxt
            self.levels.append(curr)

    def get_root(self) -> str:
        """Returns the root hash (empty string if 0 leaves, single leaf hash if 1 leaf)."""
        if not self.leaves:
            return ""
        if len(self.leaves) == 1:
            return self.leaves[0]
        return self.levels[-1][0]

    def get_proof(self, leaf_index: int) -> List[Dict[str, str]]:
        """
        Returns list of {"direction": "left" | "right", "hash": str} up to root.
        'direction' denotes the sibling's position relative to the current branch.
        """
        if leaf_index < 0 or leaf_index >= len(self.leaves):
            raise IndexError(f"leaf_index {leaf_index} out of range [0, {len(self.leaves)})")
        if len(self.leaves) <= 1:
            return []

        proof: List[Dict[str, str]] = []
        idx = leaf_index
        for lvl_idx in range(len(self.levels) - 1):
            curr_level = list(self.levels[lvl_idx])
            if len(curr_level) % 2 != 0:
                curr_level.append(curr_level[-1])

            if idx % 2 == 0:
                # Current node is left child, sibling is right
                sibling = curr_level[idx + 1]
                proof.append({"direction": "right", "hash": sibling})
            else:
                # Current node is right child, sibling is left
                sibling = curr_level[idx - 1]
                proof.append({"direction": "left", "hash": sibling})

            idx = idx // 2

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: List[Dict[str, str]], root_hash: str) -> bool:
        """Verifies whether leaf_hash reproduces root_hash given the inclusion proof."""
        if not proof:
            return leaf_hash == root_hash

        curr = leaf_hash
        for step in proof:
            direction = step.get("direction")
            sibling = step.get("hash", "")
            if direction == "right":
                curr = _node_hash(curr, sibling)
            elif direction == "left":
                curr = _node_hash(sibling, curr)
            else:
                return False

        return curr == root_hash


class EnterpriseAuditExporter:
    """Exports cryptographically audited Merkle bundles and inclusion proofs."""

    @staticmethod
    def _verify_row_hash(prev_hash: str, row: AuditEventRecord) -> bool:
        """Check hash matching either canonical JSON format or colon-delimited format."""
        # 1. Canonical JSON format (_chain_hash in auth.py)
        fields = {
            "actor": row.actor,
            "role": row.role,
            "action": row.action,
            "resource": row.resource,
            "allowed": bool(row.allowed),
            "timestamp": row.timestamp,
        }
        canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
        cand1 = hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()
        if row.entry_hash == cand1:
            return True

        # 2. Colon-delimited format
        colon_fmt = f"{prev_hash}:{row.timestamp}:{row.actor}:{row.role}:{row.action}:{row.resource}:{row.allowed}"
        cand2 = hashlib.sha256(colon_fmt.encode("utf-8")).hexdigest()
        return row.entry_hash == cand2

    @staticmethod
    async def export_bundle(
        session: AsyncSession,
        out_file: Optional[Union[Path, str]] = None,
    ) -> Dict[str, Any]:
        """
        Loads all AuditEventRecord rows ordered by seq, verifies hash chain continuity,
        constructs AuditMerkleTree, and returns or persists the audit bundle.
        """
        rows = (
            await session.execute(select(AuditEventRecord).order_by(AuditEventRecord.seq))
        ).scalars().all()

        total_events = len(rows)
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        default_genesis = "0" * 64

        if not rows:
            bundle = {
                "total_events": 0,
                "genesis_hash": default_genesis,
                "tip_hash": default_genesis,
                "merkle_root": "",
                "chain_valid": True,
                "timestamp_iso": timestamp_iso,
            }
            if out_file is not None:
                out_path = Path(out_file)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
                bundle["out_path"] = str(out_path)
            return bundle

        genesis_hash = rows[0].prev_hash or default_genesis
        tip_hash = rows[-1].entry_hash
        entry_hashes = [r.entry_hash for r in rows]

        # Verify hash chain continuity
        chain_valid = True
        expected_prev = rows[0].prev_hash
        for row in rows:
            if row.prev_hash != expected_prev:
                chain_valid = False
                break
            if not EnterpriseAuditExporter._verify_row_hash(expected_prev, row):
                chain_valid = False
                break
            expected_prev = row.entry_hash

        tree = AuditMerkleTree(entry_hashes)
        merkle_root = tree.get_root()

        bundle = {
            "total_events": total_events,
            "genesis_hash": genesis_hash,
            "tip_hash": tip_hash,
            "merkle_root": merkle_root,
            "chain_valid": chain_valid,
            "timestamp_iso": timestamp_iso,
        }

        if out_file is not None:
            out_path = Path(out_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
            bundle["out_path"] = str(out_path)

        return bundle

    @staticmethod
    async def get_inclusion_proof_for_seq(session: AsyncSession, seq: int) -> Dict[str, Any]:
        """
        Retrieves the Merkle inclusion proof for the audit record matching the given seq number.
        """
        rows = (
            await session.execute(select(AuditEventRecord).order_by(AuditEventRecord.seq))
        ).scalars().all()

        matching_indices = [i for i, r in enumerate(rows) if r.seq == seq]
        if not matching_indices:
            raise KeyError(f"Audit event with seq={seq} not found")

        leaf_idx = matching_indices[0]
        target_record = rows[leaf_idx]
        entry_hashes = [r.entry_hash for r in rows]

        tree = AuditMerkleTree(entry_hashes)
        proof = tree.get_proof(leaf_idx)

        return {
            "seq": seq,
            "entry_hash": target_record.entry_hash,
            "proof": proof,
            "merkle_root": tree.get_root(),
        }
