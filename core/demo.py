"""`keelway demo`: seed a small sample project and open the Studio on it.

The demo lives in its own folder with its own SQLite database, so it never
touches your real Keelway data. Everything it shows is produced by the real
runtime: the seeded history is an actual agent run, taped and sealed.
"""

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = Path.home() / "keelway-demo"
SEEDED_MARKER = ".keelway/seeded"
DEMO_ENTRIES = {".git", ".keelway", "money.py", "__pycache__"}
PAST_TASK_ID = "task_demo_format_cents"

FILES = {
    ".gitignore": ".keelway/\n__pycache__/\n",
    "README.md": (
        "# acme-checkout\n\n"
        "Tiny checkout service used by the Keelway demo. Prices are integer cents.\n\n"
        "Run the tests with `python3 -m unittest -q`.\n"
    ),
    "pricing.py": (
        '"""Checkout pricing. All amounts are integer cents."""\n\n\n'
        "def apply_discount(price_cents: int, percent: int) -> int:\n"
        '    """Return the price after a percentage discount, rounded to the nearest cent."""\n'
        "    return price_cents - percent\n\n\n"
        "def cart_total(items: list[tuple[int, int]], percent: int = 0) -> int:\n"
        '    """items: (unit_price_cents, quantity) pairs."""\n'
        "    subtotal = sum(price * qty for price, qty in items)\n"
        "    return apply_discount(subtotal, percent)\n"
    ),
    "test_pricing.py": (
        "import unittest\n\n"
        "from pricing import apply_discount, cart_total\n\n\n"
        "class PricingTest(unittest.TestCase):\n"
        "    def test_no_discount(self):\n"
        "        self.assertEqual(apply_discount(1000, 0), 1000)\n\n"
        "    def test_ten_percent(self):\n"
        "        self.assertEqual(apply_discount(1000, 10), 900)\n\n"
        "    def test_cart_total(self):\n"
        "        self.assertEqual(cart_total([(250, 2), (500, 1)], percent=20), 800)\n\n\n"
        'if __name__ == "__main__":\n'
        "    unittest.main()\n"
    ),
}

PAST_RUN_MONEY = (
    '"""Money formatting helpers."""\n\n\n'
    "def format_cents(cents: int, symbol: str = \"$\") -> str:\n"
    "    sign = \"-\" if cents < 0 else \"\"\n"
    "    return f\"{sign}{symbol}{abs(cents) // 100:,}.{abs(cents) % 100:02d}\"\n"
)

LIVE_GOAL = "Fix the 10% discount bug in pricing.py and prove it with the tests"
BUGGY_LINE = "    return price_cents - percent\n"
FIXED_LINE = "    return round(price_cents * (100 - percent) / 100)\n"


def _git(root: Path, *args: str) -> None:
    if not shutil.which("git"):
        raise SystemExit("keelway demo needs git on PATH (the Studio shows the agent's changes as git diffs).")
    res = subprocess.run(
        ["git", "-c", "user.name=Keelway Demo", "-c", "user.email=demo@keelway.local", "-c", "commit.gpgsign=false", *args],
        cwd=root, capture_output=True, text=True,
    )
    if res.returncode:
        raise SystemExit(f"git {' '.join(args)} failed in {root}: {res.stderr.strip()}")


def prepare_workspace(root: Path, reset: bool = False) -> Path:
    """Write the sample project (idempotent unless reset) and commit it to a fresh git repo."""
    root = root.expanduser().resolve()
    if reset and root.exists():
        entries = {p.name for p in root.iterdir()}
        if entries and (not (root / SEEDED_MARKER).exists() or not entries <= DEMO_ENTRIES | set(FILES)):
            raise SystemExit(f"Refusing to reset {root}: it is not a Keelway demo folder.")
        shutil.rmtree(root)
    if (root / SEEDED_MARKER).exists():
        return root
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"{root} already has files. Pick an empty folder with --dir.")
    _git(Path.cwd(), "--version")
    root.mkdir(parents=True, exist_ok=True)
    for name, content in FILES.items():
        (root / name).write_text(content, encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "acme-checkout: initial import")
    return root


async def seed(root: Path) -> None:
    """Seed tasks, memories and one real, sealed flight tape. Must run with cwd=root."""
    from core.orchestration.agent_loop import AutonomousAgentLoop
    from core.orchestration.state import TaskState
    from core.storage.database import AsyncSessionLocal, init_db
    from core.storage.memory import MemoryService
    from core.storage.models import TaskRecord
    from core.storage.workspace_fs import WorkspaceFilesystem

    await init_db()
    async with AsyncSessionLocal() as db:
        db.add_all([
            TaskRecord(title="Add a format_cents helper", description="Receipts need $1,234.50 style amounts.",
                       state=TaskState.COMPLETED, owner="maya", cost_usd=0.0,
                       payload={"flight_tape": PAST_TASK_ID}),
            TaskRecord(title=LIVE_GOAL, description="Customers report 10% off $10.00 shows $9.90.",
                       state=TaskState.PLANNED, owner="you"),
            TaskRecord(title="Ship receipts in Swahili and Arabic", description="Locale-aware currency strings.",
                       state=TaskState.CREATED, owner="amani"),
            TaskRecord(title="Bump the tax table for 2027", description="Needs finance sign-off before merge.",
                       state=TaskState.AWAITING_APPROVAL, owner="leo"),
        ])
        memories = MemoryService(db)
        await memories.store("money-in-cents", "All prices are integer cents. Never use floats for money.",
                             provenance_uri="pricing.py")
        await memories.store("tests", "Run tests with `python3 -m unittest -q` from the repo root.",
                             provenance_uri="README.md")
        await memories.store("release-policy", "Pricing changes need a passing test run before merge.")
        await db.commit()

    agent = AutonomousAgentLoop(task_id=PAST_TASK_ID, workspace_fs=WorkspaceFilesystem(str(root)))
    agent.initialize_plan("Add a format_cents helper", [
        "Read pricing.py to learn the money conventions",
        "Write money.py with format_cents",
        "Run the test suite",
    ])
    await agent.execute_tool("read_file", {"path": "pricing.py"}, step_id="step_1")
    await agent.execute_tool("write_file", {"path": "money.py", "content": PAST_RUN_MONEY}, step_id="step_2")
    await agent.approve_pending(True)
    await agent.execute_tool("run_command", {"command": "python3 -m unittest -q"}, step_id="step_3")
    await agent.approve_pending(True)
    agent.flight_recorder.save_tape()
    _git(root, "add", "money.py")
    _git(root, "commit", "-q", "-m", "agent: add format_cents (approved by maya)")
    (root / SEEDED_MARKER).write_text("1\n", encoding="utf-8")


def _demo_env(root: Path) -> dict:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{root / '.keelway' / 'demo.db'}"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO_ROOT), env.get("PYTHONPATH")]))
    return env


def run(directory: Path = DEFAULT_DIR, port: int = 7420, host: str = "127.0.0.1", reset: bool = False) -> int:
    """Prepare the demo folder, then serve the Studio from it in a child process with its own database."""
    root = prepare_workspace(directory, reset=reset)
    (root / ".keelway").mkdir(exist_ok=True)
    print(f"[+] Demo workspace: {root}")
    print(f"[+] Try this goal: {LIVE_GOAL}")
    cmd = [sys.executable, "-m", "core.demo", "--serve", str(root), "--port", str(port), "--host", host]
    try:
        return subprocess.call(cmd, cwd=root, env=_demo_env(root))
    except KeyboardInterrupt:
        return 0


def _serve(root: Path, port: int, host: str) -> None:
    if not (root / SEEDED_MARKER).exists():
        asyncio.run(seed(root))
    from cli import cmd_dev
    asyncio.run(cmd_dev(port, host))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="python -m core.demo")
    parser.add_argument("--serve", type=Path, required=True)
    parser.add_argument("--port", type=int, default=7420)
    parser.add_argument("--host", default="127.0.0.1")
    a = parser.parse_args()
    _serve(a.serve.resolve(), a.port, a.host)
