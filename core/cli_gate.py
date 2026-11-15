"""`keelway exec` and `keelway hook ...`: the CLI side of the Claude Code command gate (see core/agents/gate.py)."""

import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

from core.agents import gate


def _client(config: Optional[Dict[str, Any]] = None) -> gate.GateClient:
    config = config if config is not None else gate.load_gate_config()
    return gate.GateClient(gate.api_url(config), gate.gate_token(config))


def _keelway_bin() -> str:
    found = shutil.which("keelway")
    if found:
        return os.path.realpath(found)
    argv0 = Path(sys.argv[0]).resolve()
    return str(argv0) if argv0.name == "keelway" else "keelway"


def cmd_exec(ticket: str, command_parts, timeout: int = 120) -> int:
    parts = list(command_parts or [])
    if parts and parts[0] == "--":
        parts = parts[1:]
    if not parts:
        print("usage: keelway exec --ticket <ticket> -- '<command>'", file=sys.stderr)
        return 2
    command = parts[0] if len(parts) == 1 else " ".join(parts)
    return gate.run_exec(ticket, command, _client(), timeout=timeout)


def cmd_hook_gate() -> int:
    """Called by Claude Code for every PreToolUse event. Exit 0 with a JSON decision; errors become a deny."""
    try:
        event = json.loads(sys.stdin.read() or "{}")
        decision = gate.handle_hook_event(event, _client(), _keelway_bin())
    except Exception as exc:  # fail closed: an unexpected error must never let the command through
        decision = gate.deny(gate.deny_message("hook_error", detail=type(exc).__name__))
    print(json.dumps(decision))
    return 0


def _api_up(base_url: str) -> bool:
    import httpx

    try:
        return httpx.get(f"{base_url}/health", timeout=1.5).status_code == 200
    except httpx.HTTPError:
        return False


async def _mint_gate_token(name: str):
    from core.security.auth import create_api_token
    from core.security.rbac import Role
    from core.storage.database import AsyncSessionLocal, init_db

    await init_db()
    async with AsyncSessionLocal() as db:
        record, token = await create_api_token(db, name, Role.GATE)
        await db.commit()
        return record.id, token


async def _revoke_token(token_id: str) -> None:
    from datetime import datetime, timezone

    from core.storage.database import AsyncSessionLocal, init_db
    from core.storage.models import ApiTokenRecord

    await init_db()
    async with AsyncSessionLocal() as db:
        record = await db.get(ApiTokenRecord, token_id)
        if record is not None and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            await db.commit()


def cmd_hook_install(scope: str = "local", project_dir: Optional[str] = None, start: bool = True, open_browser: bool = True, port: int = 7420) -> int:
    import asyncio

    if sys.platform == "win32":
        print("Keelway's command gate needs macOS or Linux (seatbelt or bubblewrap). Native Windows is not supported in this beta.")
        return 2
    project = Path(project_dir or os.getcwd()).resolve()
    settings_file = gate.settings_path_for(scope, project)
    keelway_bin = _keelway_bin()
    old = gate.load_gate_config()
    try:
        digest = gate.install_settings(settings_file, keelway_bin)
    except ValueError as exc:
        print(f"[-] Could not update {settings_file}: {exc}")
        return 1
    token_id, token = asyncio.run(_mint_gate_token(f"gate: claude-code {project.name}"))
    base_url = os.environ.get("KEELWAY_API_URL") or f"http://127.0.0.1:{port}"
    entry = {"entries_sha256": digest, "project_dir": str(project), "installed_at": time.time()}
    installs = {**old.get("installs", {}), str(settings_file): entry}
    gate.save_gate_config({
        "token": token, "token_id": token_id, "api_url": base_url, "keelway_bin": keelway_bin,
        "settings_path": str(settings_file), **entry, "installs": installs,
    })
    if old.get("token_id"):
        asyncio.run(_revoke_token(old["token_id"]))
    print(f"✓ Hook installed ({gate.COMMAND_MATCHER}) in {settings_file}")

    studio = base_url
    if not _api_up(base_url) and start:
        owner = os.environ.get("KEELWAY_API_TOKEN") or gate.secrets.token_urlsafe(32)
        env = {**os.environ, "KEELWAY_API_TOKEN": owner}
        log = gate.keelway_home() / "dev.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "ab") as fh:
            subprocess.Popen(
                [sys.executable, "-c", "import sys, cli; sys.exit(cli.main(sys.argv[1:]))", "dev", "--port", str(port)],
                env=env, stdout=fh, stderr=fh, stdin=subprocess.DEVNULL, start_new_session=True,
            )
        for _ in range(40):
            if _api_up(base_url):
                break
            time.sleep(0.25)
        studio = f"{base_url}/?token={owner}"
        print(f"✓ Started Keelway (log: {log})")
    if not _api_up(base_url):
        print("  Keelway is not running yet. Start it with: keelway dev")
    print('  Restart Claude Code, then ask it: "run pytest -q"')
    print(f"  Approvals appear at {base_url}")
    if open_browser:
        try:
            webbrowser.open(studio)
        except Exception:
            pass
    return 0


def cmd_hook_uninstall(scope: str = "local", project_dir: Optional[str] = None) -> int:
    import asyncio

    config = gate.load_gate_config()
    settings_file = gate.settings_path_for(scope, Path(project_dir or os.getcwd()).resolve())
    removed = gate.uninstall_settings(settings_file)
    installs = {k: v for k, v in config.get("installs", {}).items() if k != str(settings_file)}
    if installs:
        path, entry = next(iter(installs.items()))
        gate.save_gate_config({**config, "settings_path": path, **entry, "installs": installs})
        print(f"✓ Removed {removed} Keelway hook entr{'y' if removed == 1 else 'ies'} from {settings_file}; "
              f"{len(installs)} other install(s) keep the gate token.")
        return 0
    if config.get("token_id"):
        asyncio.run(_revoke_token(config["token_id"]))
    try:
        gate.gate_config_path().unlink()
    except FileNotFoundError:
        pass
    print(f"✓ Removed {removed} Keelway hook entr{'y' if removed == 1 else 'ies'} from {settings_file}; gate token revoked.")
    return 0


def first_approval_seconds(project: Path, installed_at: float) -> Optional[float]:
    """Install -> first approved command, read from the local gate tapes. Nothing leaves the machine."""
    first: Optional[float] = None
    for tape in (project / ".keelway" / "recordings").glob("gate-*.flight.json"):
        try:
            events = json.loads(tape.read_text(encoding="utf-8")).get("events", [])
        except (OSError, ValueError):
            continue
        for ev in events:
            ts = float(ev.get("timestamp_utc") or 0)
            if ev.get("event_type") == "gate_decided" and (ev.get("payload") or {}).get("decision") == gate.APPROVED and ts >= installed_at:
                first = ts if first is None else min(first, ts)
    return None if first is None else first - installed_at


def hook_health(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Shared with doctor: is the hook installed, untampered, and able to reach the API?"""
    config = config if config is not None else gate.load_gate_config()
    if not config.get("settings_path"):
        return {"installed": False, "tampered": False, "api": False, "detail": "not installed (run: keelway hook install --claude-code)"}
    current = gate.installed_entries_sha256(Path(config["settings_path"]))
    tampered = current != config.get("entries_sha256")
    api = _api_up(gate.api_url(config))
    if current is None:
        detail = f"hook entries missing from {config['settings_path']} (run: keelway hook install --claude-code)"
    elif tampered:
        detail = f"hook entries in {config['settings_path']} changed since install (run: keelway hook install --claude-code)"
    elif not api:
        detail = "installed, but Keelway is not running (start it with: keelway dev)"
    else:
        detail = "installed and untampered"
    return {"installed": current is not None, "tampered": tampered and current is not None, "api": api, "detail": detail,
            "settings_path": config["settings_path"]}


def cmd_hook_status() -> int:
    config = gate.load_gate_config()
    health = hook_health(config)
    mark = "✓" if health["installed"] and not health["tampered"] else "✗"
    print(f"{mark} Claude Code hook: {health['detail']}")
    if not health.get("settings_path"):
        return 2
    print(f"  API: {gate.api_url(config)} ({'reachable' if health['api'] else 'not reachable'})")
    seconds = first_approval_seconds(Path(config.get("project_dir") or os.getcwd()), float(config.get("installed_at") or 0))
    if seconds is None:
        print("  First approved command: none yet")
    else:
        print(f"  First approved command: {int(seconds // 60)}m{int(seconds % 60):02d}s after install")
    if not health["installed"] or health["tampered"]:
        return 2
    return 0 if health["api"] else 1
