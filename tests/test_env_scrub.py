import json
import os
import re
from pathlib import Path

import pytest

from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.orchestration.self_healing import SelfHealingLoop
from core.orchestration.workflows.sandboxed_test_analysis import SandboxedFailureAnalysisWorkflow
from core.security.env_scrub import PASSTHROUGH_VAR, is_secret, scrub_env
from core.storage.workspace_fs import WorkspaceFilesystem

SECRET_VALUE = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

KEEP = {
    "PATH": "/usr/bin:/bin", "HOME": "/Users/me", "LANG": "en_US.UTF-8", "TERM": "xterm", "VIRTUAL_ENV": "/p/.venv",
    "PYTHONPATH": "/p", "PYTHONUNBUFFERED": "1", "EDITOR": "vim", "NO_COLOR": "1", "AUTHOR": "me",
    "TOKENIZERS_PARALLELISM": "false", "DATABASE_URL": "sqlite+aiosqlite:///./k.db", "REDIS_URL": "redis://localhost:6379/0",
    "HOMEBREW_PREFIX": "/opt/homebrew", "SK_LEARN_SEED": "sk-learn", "ALLOWED_ORIGINS": "http://localhost:7420",
}


@pytest.mark.parametrize("name,value", sorted(KEEP.items()))
def test_ordinary_variables_survive(name, value):
    assert not is_secret(name, value)
    assert scrub_env({name: value})[0] == {name: value}


@pytest.mark.parametrize("name", [
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "NVIDIA_API_KEY", "AUTH_SECRET", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET",
    "GITHUB_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS", "KEELWAY_API_TOKEN", "KEELWAY_DEV_CLI", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "AWS_PROFILE", "AZURE_CLIENT_SECRET", "SSH_AUTH_SOCK", "DB_PASSWORD", "MY_SERVICE_TOKEN", "STRIPE_SECRET_KEY", "NPM_CONFIG__AUTHTOKEN",
    "ANTHROPIC_MODEL", "lowercase_api_key", "SESSION_COOKIE", "PGPASSWORD_FILE_TOKEN",
])
def test_secret_looking_names_are_removed(name):
    clean, dropped = scrub_env({name: "x", "PATH": "/usr/bin"})
    assert name not in clean and name in dropped and clean["PATH"] == "/usr/bin"


@pytest.mark.parametrize("value", [
    "postgresql://admin:hunter2@db.internal:5432/app", "redis://:secretpw@cache:6379", SECRET_VALUE,
    "ghp_" + "a" * 36, "AKIAABCDEFGHIJKLMNOP", "xoxb-1234567890-abcdefghij", "-----BEGIN RSA PRIVATE KEY-----\nMIIE",
])
def test_secret_looking_values_are_removed_under_innocent_names(value):
    clean, dropped = scrub_env({"INNOCENT_SETTING": value})
    assert "INNOCENT_SETTING" not in clean and dropped == ["INNOCENT_SETTING"]


def test_dropped_list_has_names_only_and_input_is_not_mutated():
    parent = {"ANTHROPIC_API_KEY": SECRET_VALUE, "PATH": "/bin", "B_TOKEN": "t", "A_TOKEN": "t"}
    before = dict(parent)
    clean, dropped = scrub_env(parent)
    assert parent == before and dropped == ["ANTHROPIC_API_KEY", "A_TOKEN", "B_TOKEN"]
    assert SECRET_VALUE not in repr(dropped) and clean == {"PATH": "/bin"}


def test_operator_passthrough_keeps_only_the_named_variables():
    parent = {PASSTHROUGH_VAR: "GITHUB_TOKEN, NOT_SET", "GITHUB_TOKEN": "ghp_" + "a" * 36, "ANTHROPIC_API_KEY": SECRET_VALUE, "PATH": "/bin"}
    clean, dropped = scrub_env(parent)
    assert clean == {"PATH": "/bin", "GITHUB_TOKEN": "ghp_" + "a" * 36}
    assert PASSTHROUGH_VAR in dropped and "ANTHROPIC_API_KEY" in dropped  # the setting itself is not forwarded either


def test_every_secret_listed_in_env_example_is_covered():
    repo_root = Path(__file__).resolve().parent.parent
    dot_env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    legacy_env_example = (repo_root / "env.example").read_text(encoding="utf-8")
    assert dot_env_example == legacy_env_example, ".env.example and env.example must remain in sync"

    names = re.findall(r"^([A-Z][A-Z0-9_]*)=", dot_env_example, re.M)
    harmless = {
        "LOCAL_MODEL_BASE_URL", "LOCAL_MODEL_NAME", "DEFAULT_MODEL_PROVIDER", "DEFAULT_MODEL",
        "AUTH_REQUIRED", "GOOGLE_CLOUD_PROJECT", "OTEL_EXPORTER_OTLP_ENDPOINT", "ALLOWED_ORIGINS",
        "EARLY_ACCESS_ALLOWED_ORIGINS", "GOOGLE_MODEL", "NVIDIA_MODEL", "OPENAI_MODEL",
        "ANTHROPIC_MODEL", "OIDC_CLIENT_ID",
    }
    secret_looking = [n for n in names if n not in harmless]
    assert secret_looking, "env.example parsing found nothing"
    assert all(is_secret(n, "x") for n in secret_looking), [n for n in secret_looking if not is_secret(n, "x")]


# ---- the three runners ------------------------------------------------------

@pytest.fixture
def secrets_in_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET_VALUE)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_" + "b" * 36)
    monkeypatch.setenv("DATABASE_URL_WITH_PW", "postgresql://u:pw123@h/db")
    monkeypatch.setenv("KEEP_ME", "visible")
    monkeypatch.delenv(PASSTHROUGH_VAR, raising=False)


def assert_clean(text):
    assert "KEEP_ME=visible" in text
    for leaked in (SECRET_VALUE, "ghp_" + "b" * 36, "pw123", "ANTHROPIC_API_KEY"):
        assert leaked not in text


@pytest.mark.asyncio
async def test_agent_run_command_without_verified_isolation_does_not_start(tmp_path, secrets_in_env):
    agent = AutonomousAgentLoop("t", WorkspaceFilesystem(str(tmp_path)), policy=AutonomyPolicy.AUTONOMOUS, record_flight=False)
    res = await agent.execute_tool("run_command", {"command": "env"})
    assert res["status"] == "error"
    assert "unavailable" in res["error"].lower()
    assert "stdout" not in res
    shell = await agent.execute_tool("run_command", {"command": "echo $ANTHROPIC_API_KEY-end; echo $PATH"})
    assert shell["status"] == "error"
    assert SECRET_VALUE not in json.dumps(shell)


@pytest.mark.asyncio
async def test_agent_run_command_passthrough_cannot_reach_a_host_shell(tmp_path, secrets_in_env, monkeypatch):
    monkeypatch.setenv(PASSTHROUGH_VAR, "GITHUB_TOKEN")
    agent = AutonomousAgentLoop("t", WorkspaceFilesystem(str(tmp_path)), policy=AutonomyPolicy.AUTONOMOUS, record_flight=False)
    res = await agent.execute_tool("run_command", {"command": "env"})
    text = json.dumps(res)
    assert res["status"] == "error"
    assert "unavailable" in res["error"].lower()
    assert "ghp_" + "b" * 36 not in text and SECRET_VALUE not in text


@pytest.mark.asyncio
async def test_sandboxed_test_workflow_no_longer_passes_the_environment_through(tmp_path, secrets_in_env):
    res = await SandboxedFailureAnalysisWorkflow(workspace_root=tmp_path).execute_sandboxed_tests("env")
    assert res["exit_code"] == 0
    assert_clean(res["stdout"])


@pytest.mark.asyncio
async def test_self_healing_test_runs_do_not_see_secrets_but_keep_pythonpath(tmp_path, secrets_in_env):
    code, out, _ = await SelfHealingLoop(repo_root=tmp_path).execute_test("env", cwd=tmp_path)
    assert code == 0
    assert_clean(out)
    assert f"PYTHONPATH={tmp_path}" in out
