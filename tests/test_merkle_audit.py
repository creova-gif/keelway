"""
Comprehensive tests for Enterprise Merkle Audit & Cryptographic Inclusion Proofs.
Tests AuditMerkleTree construction, proof generation, tampering detection,
EnterpriseAuditExporter hash chain continuity, REST API endpoints, and CLI dispatch.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from cli import build_parser, cmd_audit
from core.api import routes
from core.main import app
from core.security.merkle_audit import AuditMerkleTree, EnterpriseAuditExporter
from core.storage.database import AsyncSessionLocal, init_db
from core.storage.workspace_fs import WorkspaceFilesystem


@pytest.fixture
def workspace_fixture():
    """
    Temporary workspace fixture ensuring routes._workspace_fs is cleanly restored
    in a try...finally block.
    """
    prev_fs = routes._workspace_fs
    tmp_dir = tempfile.mkdtemp(prefix="keelway_merkle_test_")
    fs = WorkspaceFilesystem(root_dir=tmp_dir)
    routes.set_workspace_fs(fs)
    try:
        yield Path(tmp_dir)
    finally:
        routes.set_workspace_fs(prev_fs)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# =====================================================================
# 1. Unit Tests: AuditMerkleTree (1, 2, 3, 8 leaves & verification)
# =====================================================================

def test_merkle_tree_empty_and_single_leaf():
    """Test tree with 0 and 1 leaf."""
    t0 = AuditMerkleTree([])
    assert t0.get_root() == ""
    with pytest.raises(IndexError):
        t0.get_proof(0)

    leaf = hashlib.sha256(b"event_0").hexdigest()
    t1 = AuditMerkleTree([leaf])
    assert t1.get_root() == leaf
    proof1 = t1.get_proof(0)
    assert proof1 == []
    assert AuditMerkleTree.verify_proof(leaf, proof1, t1.get_root()) is True


def test_merkle_tree_two_leaves():
    """Test tree with 2 leaves."""
    l0 = hashlib.sha256(b"event_0").hexdigest()
    l1 = hashlib.sha256(b"event_1").hexdigest()
    expected_root = hashlib.sha256((l0 + l1).encode("utf-8")).hexdigest()

    tree = AuditMerkleTree([l0, l1])
    assert tree.get_root() == expected_root

    # Leaf 0 proof: sibling is l1 on the right
    p0 = tree.get_proof(0)
    assert len(p0) == 1
    assert p0[0] == {"direction": "right", "hash": l1}
    assert AuditMerkleTree.verify_proof(l0, p0, expected_root) is True

    # Leaf 1 proof: sibling is l0 on the left
    p1 = tree.get_proof(1)
    assert len(p1) == 1
    assert p1[0] == {"direction": "left", "hash": l0}
    assert AuditMerkleTree.verify_proof(l1, p1, expected_root) is True


def test_merkle_tree_three_leaves_odd_duplication():
    """Test tree with 3 leaves verifying odd node duplication at leaf level."""
    leaves = [hashlib.sha256(f"event_{i}".encode("utf-8")).hexdigest() for i in range(3)]
    tree = AuditMerkleTree(leaves)
    root = tree.get_root()
    assert len(root) == 64

    for i in range(3):
        proof = tree.get_proof(i)
        assert AuditMerkleTree.verify_proof(leaves[i], proof, root) is True


def test_merkle_tree_eight_leaves_full_verification():
    """Test full binary tree with 8 leaves."""
    leaves = [hashlib.sha256(f"payload_{i}".encode("utf-8")).hexdigest() for i in range(8)]
    tree = AuditMerkleTree(leaves)
    root = tree.get_root()

    for idx in range(8):
        proof = tree.get_proof(idx)
        assert len(proof) == 3  # log2(8) = 3 levels of proofs
        assert AuditMerkleTree.verify_proof(leaves[idx], proof, root) is True


def test_merkle_tree_tamper_rejection():
    """Verify that tampering with leaf hash, proof hash, direction, or root fails verification."""
    leaves = [hashlib.sha256(f"event_{i}".encode("utf-8")).hexdigest() for i in range(4)]
    tree = AuditMerkleTree(leaves)
    root = tree.get_root()
    proof = tree.get_proof(0)

    # 1. Tampered leaf hash
    tampered_leaf = hashlib.sha256(b"tampered_data").hexdigest()
    assert AuditMerkleTree.verify_proof(tampered_leaf, proof, root) is False

    # 2. Tampered proof hash
    bad_proof = [{"direction": step["direction"], "hash": "0" * 64} for step in proof]
    assert AuditMerkleTree.verify_proof(leaves[0], bad_proof, root) is False

    # 3. Tampered direction
    flipped_proof = [{"direction": "left" if step["direction"] == "right" else "right", "hash": step["hash"]} for step in proof]
    assert AuditMerkleTree.verify_proof(leaves[0], flipped_proof, root) is False

    # 4. Wrong root
    wrong_root = hashlib.sha256(b"wrong_root").hexdigest()
    assert AuditMerkleTree.verify_proof(leaves[0], proof, wrong_root) is False


# =====================================================================
# 2. Database Hash Chain & EnterpriseAuditExporter Tests
# =====================================================================

@pytest.mark.asyncio
async def test_enterprise_audit_exporter_db_chain(tmp_path: Path):
    """Test generating and exporting an Enterprise Audit Merkle bundle from real DB rows."""
    await init_db()
    from core.security.auth import LOCAL_OWNER, record_audit

    # Add 5 audit events to the real chain
    for i in range(1, 6):
        await record_audit(LOCAL_OWNER, f"merkle_action_{i}", f"/workspace/file_{i}.py", True)

    async with AsyncSessionLocal() as session:
        # Export bundle
        out_json = tmp_path / "merkle_bundle.json"
        bundle = await EnterpriseAuditExporter.export_bundle(session, out_file=out_json)

        assert bundle["total_events"] >= 5
        assert bundle["chain_valid"] is True
        assert bundle["merkle_root"] != ""
        assert out_json.is_file()

        # Test inclusion proof retrieval for seq=1
        proof_res = await EnterpriseAuditExporter.get_inclusion_proof_for_seq(session, 1)
        assert proof_res["seq"] == 1
        assert "entry_hash" in proof_res
        assert AuditMerkleTree.verify_proof(proof_res["entry_hash"], proof_res["proof"], proof_res["merkle_root"]) is True


# =====================================================================
# 3. REST API Endpoints Tests
# =====================================================================

@pytest.mark.asyncio
async def test_merkle_audit_rest_api_endpoints(workspace_fixture: Path):
    """Test /v1/audit/merkle/root, /v1/audit/merkle/proof/{seq}, /v1/audit/merkle/verify, /v1/audit/export/bundle."""
    await init_db()

    # Seed one audit entry if DB is empty
    from core.security.auth import LOCAL_OWNER, record_audit
    await record_audit(LOCAL_OWNER, "merkle_test_action", "resource_test", True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET Merkle root
        root_resp = await client.get(
            "/v1/audit/merkle/root",
            headers={"X-Keelway-Actor": "auditor", "X-Keelway-Role": "platform_owner"},
        )
        assert root_resp.status_code == 200, root_resp.text
        root_data = root_resp.json()
        assert "merkle_root" in root_data
        assert root_data["total_events"] >= 1
        root_hash = root_data["merkle_root"]

        # 2. GET Merkle proof for seq=1
        proof_resp = await client.get(
            "/v1/audit/merkle/proof/1",
            headers={"X-Keelway-Actor": "auditor", "X-Keelway-Role": "platform_owner"},
        )
        assert proof_resp.status_code == 200, proof_resp.text
        proof_data = proof_resp.json()
        assert proof_data["seq"] == 1
        leaf_hash = proof_data["entry_hash"]
        proof_steps = proof_data["proof"]

        # 3. POST verify proof (Valid)
        verify_resp = await client.post(
            "/v1/audit/merkle/verify",
            json={
                "leaf_hash": leaf_hash,
                "proof": proof_steps,
                "root_hash": root_hash,
            },
            headers={"X-Keelway-Actor": "auditor", "X-Keelway-Role": "platform_owner"},
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["valid"] is True

        # 4. POST verify proof (Tampered)
        verify_bad = await client.post(
            "/v1/audit/merkle/verify",
            json={
                "leaf_hash": "f" * 64,
                "proof": proof_steps,
                "root_hash": root_hash,
            },
            headers={"X-Keelway-Actor": "auditor", "X-Keelway-Role": "platform_owner"},
        )
        assert verify_bad.status_code == 200
        assert verify_bad.json()["valid"] is False

        # 5. POST export bundle
        bundle_resp = await client.post(
            "/v1/audit/export/bundle",
            json={},
            headers={"X-Keelway-Actor": "auditor", "X-Keelway-Role": "platform_owner"},
        )
        assert bundle_resp.status_code == 200
        bundle_json = bundle_resp.json()
        assert "merkle_root" in bundle_json
        assert bundle_json["total_events"] >= 1


# =====================================================================
# 4. CLI Tests (keelway audit proof, verify-proof, export)
# =====================================================================

def test_cli_audit_parser():
    """Verify build_parser registers audit proof, verify-proof, and export."""
    parser = build_parser()

    # audit proof
    args_prf = parser.parse_args(["audit", "proof", "3"])
    assert args_prf.command == "audit"
    assert args_prf.audit_command == "proof"
    assert args_prf.seq == 3

    # audit verify-proof
    args_vp = parser.parse_args([
        "audit", "verify-proof",
        "a" * 64,
        json.dumps([{"direction": "left", "hash": "b" * 64}]),
        "r" * 64,
    ])
    assert args_vp.command == "audit"
    assert args_vp.audit_command == "verify-proof"
    assert args_vp.leaf_hash == "a" * 64
    assert args_vp.root_hash == "r" * 64

    # audit export
    args_exp = parser.parse_args(["audit", "export", "--out", "bundle.json"])
    assert args_exp.command == "audit"
    assert args_exp.audit_command == "export"
    assert args_exp.out == Path("bundle.json")


@pytest.mark.asyncio
async def test_cli_audit_execution(tmp_path: Path):
    """Test cmd_audit execution for proof, verify-proof, and export."""
    # 1. Export
    bundle_file = tmp_path / "cli_bundle.json"
    rc_exp = await cmd_audit("export", path=bundle_file)
    assert rc_exp == 0
    assert bundle_file.is_file()

    # 2. Verify-proof (Valid computation)
    l0 = hashlib.sha256(b"leaf0").hexdigest()
    l1 = hashlib.sha256(b"leaf1").hexdigest()
    root = hashlib.sha256((l0 + l1).encode("utf-8")).hexdigest()
    proof_json = json.dumps([{"direction": "right", "hash": l1}])

    rc_valid = await cmd_audit("verify-proof", leaf_hash=l0, proof=proof_json, root_hash=root)
    assert rc_valid == 0

    # 3. Verify-proof (Invalid computation)
    rc_invalid = await cmd_audit("verify-proof", leaf_hash=l0, proof=proof_json, root_hash="f" * 64)
    assert rc_invalid == 1
