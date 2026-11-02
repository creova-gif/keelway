import json

import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.security import record_format as rf
from core.security.auth import GENESIS_HASH, _chain_hash, launch_token

pytestmark = pytest.mark.auth


def _entry(prev, n, allowed=True):
    fields = {"actor": "a", "role": "owner", "action": "x", "resource": f"GET /{n}", "allowed": allowed, "timestamp": f"2026-01-01T00:00:0{n}+00:00"}
    return {"seq": n, "prev_hash": prev, **fields, "entry_hash": rf.entry_hash(prev, fields)}


def _chain(n=3):
    out, prev = [], rf.GENESIS_HASH
    for i in range(1, n + 1):
        e = _entry(prev, i)
        out.append(e)
        prev = e["entry_hash"]
    return out


def test_format_matches_the_product_chain_hash():
    # The standalone format must stay byte-compatible with what the server writes.
    assert rf.GENESIS_HASH == GENESIS_HASH
    fields = {"actor": "a", "role": "owner", "action": "x", "resource": "r", "allowed": False, "timestamp": "t"}
    assert rf.entry_hash(GENESIS_HASH, fields) == _chain_hash(GENESIS_HASH, fields)


def test_valid_chain_with_header_verifies():
    entries = _chain()
    result = rf.verify_entries(entries, rf.make_header(entries))
    assert result == {"valid": True, "entries": 3, "head": entries[-1]["entry_hash"]}


def test_empty_log_is_valid():
    assert rf.verify_entries([], rf.make_header([]))["valid"] is True


@pytest.mark.parametrize("mutate,reason", [
    (lambda es: es[1].update(action="evil"), "entry_hash_mismatch"),
    (lambda es: es[1].update(allowed=False), "entry_hash_mismatch"),
    (lambda es: es.pop(1), "prev_hash_mismatch"),
    (lambda es: es.reverse(), "prev_hash_mismatch"),
    (lambda es: es[0].update(prev_hash="f" * 64), "prev_hash_mismatch"),
    (lambda es: es[2].pop("resource"), "missing_field"),
    (lambda es: es[0].update(allowed="yes"), "wrong_type"),
])
def test_any_tampering_is_detected(mutate, reason):
    entries = _chain()
    mutate(entries)
    result = rf.verify_entries(entries)
    assert result["valid"] is False and result["reason"] == reason


def test_header_catches_dropped_tail_and_wrong_format():
    entries = _chain()
    header = rf.make_header(entries)
    assert rf.verify_entries(entries[:-1], header)["reason"] == "header_count_mismatch"
    assert rf.verify_entries(entries, {**header, "format": "other/v9"})["reason"] == "unsupported_format"
    forged = {**header, "head": "0" * 64}
    assert rf.verify_entries(entries, forged)["reason"] == "header_head_mismatch"


def test_jsonl_round_trip_and_cli(tmp_path, capsys):
    entries = _chain()
    path = tmp_path / "log.jsonl"
    path.write_text(rf.dump_jsonl(entries))
    assert rf.main(["verify", str(path)]) == 0
    assert "chain valid: 3 entries" in capsys.readouterr().out
    lines = path.read_text().splitlines()
    lines[2] = lines[2].replace('"action": "x"', '"action": "y"')
    path.write_text("\n".join(lines) + "\n")
    assert rf.main(["verify", str(path)]) == 1
    assert "BROKEN at entry #2" in capsys.readouterr().out
    assert rf.main(["verify", str(tmp_path / "missing.jsonl")]) == 2
    path.write_text("{not json\n")
    assert rf.main(["verify", str(path)]) == 2


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_exported_live_log_verifies_standalone_and_detects_edits(client, tmp_path):
    from core.security.record_export import export_record

    owner = {"Authorization": f"Bearer {launch_token()}"}
    created = client.post("/v1/auth/tokens", json={"name": "aud", "role": "auditor"}, headers=owner).json()
    aud = {"Authorization": f"Bearer {created['token']}"}
    client.post("/v1/tasks", json={"title": "Denied task"}, headers=aud)
    client.get("/v1/tasks", headers=aud)

    path = tmp_path / "record.jsonl"
    summary = await export_record(path)
    assert summary["valid"] is True and summary["entries"] >= 3

    lines = path.read_text().splitlines()
    assert json.loads(lines[0])["format"] == rf.FORMAT
    assert rf.main(["verify", str(path)]) == 0

    forged = json.loads(lines[2])
    forged["allowed"] = not forged["allowed"]
    lines[2] = json.dumps(forged, sort_keys=True)
    path.write_text("\n".join(lines) + "\n")
    assert rf.main(["verify", str(path)]) == 1
