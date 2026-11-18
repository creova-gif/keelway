"""ADR-0045 enforcement: the zero-dependency fallback server owns no /v1 paths.

`core.main:app` is the single API authority. The static fallback must degrade
honestly (503 + api_available:false), never serve stub resource data, and never
touch the service layer (WorkspaceFilesystem, CodebaseSemanticIndex, agent runs).
"""

import json
import socketserver
import threading
import urllib.request
import urllib.error

import pytest

from core.api.fallback_server import StaticFallbackHandler


@pytest.fixture()
def fallback_url():
    server = socketserver.TCPServer(("127.0.0.1", 0), StaticFallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.loads(r.read() or b"null"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null"), dict(e.headers)


def _post(url: str, payload: dict):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def test_fallback_serves_studio_shell_and_degraded_health(fallback_url):
    status, body, headers = _get(f"{fallback_url}/health")
    assert status == 200
    assert body == {"status": "degraded", "mode": "static_fallback", "api_available": False}

    with urllib.request.urlopen(f"{fallback_url}/", timeout=5) as r:
        assert r.status == 200
        assert "text/html" in r.headers["Content-Type"]
        assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
        assert r.read() == StaticFallbackHandler.studio_html_path.read_bytes()


@pytest.mark.parametrize("path", [
    "/v1/flight/tapes",
    "/v1/mesh/peers",
    "/v1/agent/status",
    "/v1/files/tree",
    "/v1/files/content?path=a.txt",
    "/v1/git/status",
    "/v1/index/search?q=x",
    "/v1/approval-rules",
])
def test_every_v1_get_returns_honest_503(fallback_url, path):
    status, body, _ = _get(f"{fallback_url}{path}")
    assert status == 503
    assert body["api_available"] is False
    # No stub resource data may leak through
    assert "tapes" not in body and "results" not in body and "active_peers" not in body


def test_v1_post_file_save_is_refused_and_writes_nothing(fallback_url, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status, body = _post(f"{fallback_url}/v1/files/save", {"path": "evil.txt", "content": "x"})
    assert status == 503
    assert body["api_available"] is False
    assert not (tmp_path / "evil.txt").exists()


def test_v1_post_agent_run_returns_no_fabricated_plan(fallback_url):
    status, body = _post(f"{fallback_url}/v1/agent/run", {"goal": "g"})
    assert status == 503
    assert "task_id" not in body and "state" not in body


def test_cli_dev_path_contains_no_shadow_v1_handlers():
    """Source-level guard: cli.py may not re-implement /v1 endpoints outside core/api/."""
    import pathlib
    import re
    source = (pathlib.Path(__file__).resolve().parent.parent / "cli.py").read_text(encoding="utf-8")
    shadow = re.findall(r'self\.path\s*(?:==|\.startswith\()\s*"/v1/', source)
    assert shadow == [], f"cli.py re-implements /v1 handlers: {shadow}"
