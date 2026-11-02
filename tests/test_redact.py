import copy
import json
from pathlib import Path

import pytest

from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.orchestration.flight_recorder import FlightPlayer, FlightRecorder
from core.security.redact import redact_payload, redact_text
from core.storage.workspace_fs import WorkspaceFilesystem

OPENAI = "sk-proj-FAKEFAKEFAKEFAKEFAKEFAKE1234567890"
GH = "ghp_" + "a" * 36
SLACK = "xoxb-1234567890-abcdefghij"


@pytest.mark.parametrize("text,secret", [
    (f"OPENAI_API_KEY={OPENAI}", OPENAI),
    ("DB=postgresql://admin:hunter2@db.internal/prod", "hunter2"),
    ("REDIS_URL=redis://:pw123secret@cache:6379/0", "pw123secret"),
    ("origin https://bot:s3cr3tpass@github.com/org/repo.git", "s3cr3tpass"),
    (f"remote token {GH}", GH),
    (f"slack {SLACK}", SLACK),
    ("AKIAABCDEFGHIJKLMNOP", "AKIAABCDEFGHIJKLMNOP"),
    ("JWT_SECRET=correct-horse-battery", "correct-horse-battery"),
    ("export STRIPE_SECRET_KEY=abc123def456", "abc123def456"),
    ("password: hunter2", "hunter2"),
    ("db_password = hunter2", "hunter2"),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\nabc\n-----END RSA PRIVATE KEY-----", "MIIEowIBAAKCAQEA"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk\n", "b3BlbnNzaC1rZXk"),  # cut off before END
])
def test_secrets_are_removed_from_text(text, secret):
    clean, count = redact_text(text)
    assert secret not in clean and count >= 1 and "[REDACTED_" in clean


@pytest.mark.parametrize("text", [
    "", "plain prose with no secrets", "def add(a, b):\n    return a + b", "max_tokens = 256", "tokenizer = load()",
    "AUTHOR=Jane Doe", "DATABASE_URL=sqlite+aiosqlite:///./kora.db", "http://localhost:7420/?x=1", "redis://localhost:6379/0",
    "https://example.com/a@b", "sk-learn is a library", "ssh-rsa AAAAB3NzaC1yc2E user@host",
])
def test_ordinary_text_is_left_alone(text):
    assert redact_text(text) == (text, 0)


def test_the_same_secret_is_not_redacted_twice_or_left_half_done():
    clean, _ = redact_text(f"DB_PASSWORD=hunter2\nOPENAI_API_KEY={OPENAI}\nurl postgres://u:hunter2@h/db")
    assert "hunter2" not in clean and OPENAI not in clean
    assert redact_text(clean) == (clean, 0)  # idempotent: nothing left to find, and no [REDACTED] inside [REDACTED]
    assert "[REDACTED_[REDACTED" not in clean


def test_payloads_are_redacted_deeply_by_value_and_by_key_without_touching_the_input():
    payload = {
        "tool": "read_file", "ok": True, "n": 3, "none": None,
        "arguments": {"path": ".env", "headers": {"Authorization": "Bearer abcdefghijklmnopqrstuvwxyz0123", "X-Trace": "t1"}},
        "result": {"content": f"A=1\nOPENAI_API_KEY={OPENAI}\n", "lines": [f"x {GH}", "plain"], "tuple": (f"y {SLACK}",)},
        "api_key": "short",
        "max_tokens": 256,
    }
    before = copy.deepcopy(payload)
    clean, count = redact_payload(payload)
    assert payload == before  # input untouched
    blob = json.dumps(clean)
    for leaked in (OPENAI, GH, SLACK, "abcdefghijklmnopqrstuvwxyz0123", "short"):
        assert leaked not in blob
    assert clean["max_tokens"] == 256 and clean["n"] == 3 and clean["none"] is None and clean["arguments"]["headers"]["X-Trace"] == "t1"
    assert clean["arguments"]["path"] == ".env" and clean["result"]["lines"][1] == "plain"
    assert isinstance(clean["result"]["tuple"], tuple) and count >= 5


# ---- the flight recorder -------------------------------------------------------

def test_recorder_never_stores_secrets_and_counts_what_it_removed(tmp_path):
    rec = FlightRecorder("t1", recordings_dir=tmp_path)
    rec.record_event("tool:read_file", {"result": {"content": f"OPENAI_API_KEY={OPENAI}"}})
    rec.record_event("tool:run_command", {"result": {"stdout": "DB=postgresql://admin:hunter2@h/db\nGH=" + GH}})
    rec.record_event("state", {"note": "nothing sensitive"})
    assert OPENAI not in json.dumps([e.payload for e in rec.events])
    path = rec.save_tape()
    text = path.read_text()
    for leaked in (OPENAI, "hunter2", GH):
        assert leaked not in text
    saved = json.loads(text)
    assert saved["redactions"] >= 3 and saved["event_count"] == 3
    assert saved["events"][2]["payload"] == {"note": "nothing sensitive"}


def test_tape_is_still_valid_and_replayable_after_redaction(tmp_path):
    rec = FlightRecorder("t2", recordings_dir=tmp_path)
    rec.record_event("tool:read_file", {"result": {"content": f"K={OPENAI}\nline two"}})
    player = FlightPlayer(rec.save_tape())
    event = player.step_forward()
    assert "line two" in event["payload"]["result"]["content"] and OPENAI not in json.dumps(event)


def test_forking_a_tape_does_not_resurrect_secrets(tmp_path):
    rec = FlightRecorder("t3", recordings_dir=tmp_path)
    rec.record_event("tool:read_file", {"result": {"content": f"K={OPENAI}"}})
    player = FlightPlayer(rec.save_tape())
    forked = player.fork(1, "t3-fork")
    forked.recordings_dir = tmp_path
    assert OPENAI not in forked.save_tape().read_text()


# ---- the scenario that failed before: an agent reads .env --------------------------

@pytest.mark.asyncio
async def test_secrets_an_agent_reads_do_not_reach_the_saved_tape(tmp_path):
    (tmp_path / ".env").write_text(f"OPENAI_API_KEY={OPENAI}\nJWT_SECRET=correct-horse-battery\n")
    (tmp_path / "config.txt").write_text("DB=postgresql://admin:hunter2@db/prod\n")
    agent = AutonomousAgentLoop("tapetest", WorkspaceFilesystem(str(tmp_path)), policy=AutonomyPolicy.AUTONOMOUS, record_flight=True)
    agent.flight_recorder.recordings_dir = tmp_path / "rec"
    agent.initialize_plan("g", ["s"])
    first = await agent.execute_tool("read_file", {"path": ".env"})
    assert first["status"] == "success"  # the agent really did read the secret file
    await agent.execute_tool("read_file", {"path": "config.txt"})
    await agent.execute_tool("run_command", {"command": "cat .env"})
    text = agent.flight_recorder.save_tape().read_text()
    for leaked in (OPENAI, "correct-horse-battery", "hunter2"):
        assert leaked not in text, leaked
    assert json.loads(text)["redactions"] >= 3
