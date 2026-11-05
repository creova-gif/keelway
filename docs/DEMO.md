# Demo: `keelway demo`

One command seeds a sample project and opens the Studio on it. The demo has its own folder, git repo and SQLite database, so it never touches your real Keelway data.

```bash
pip install -r requirements.txt
python cli.py demo                # ~/keelway-demo, http://127.0.0.1:7420
python cli.py demo --reset        # wipe and re-seed
python cli.py demo --dir /tmp/kd --port 7431
```

The command prints a Studio URL with a launch token. Set `KEELWAY_API_TOKEN` if you want a fixed token.

## What gets seeded

- `acme-checkout`: a tiny checkout service with a real bug. `apply_discount(1000, 10)` returns `990` instead of `900`. The `unittest` tests fail until it is fixed.
- Four tasks in different states, plus three project memories (integer cents, test command, release policy).
- One sealed flight tape (`task_demo_format_cents`) recorded by the real `AutonomousAgentLoop`: read, approved write, approved test run.

`keelway demo` refuses to reuse a folder it did not create. Running it again reuses the seeded workspace unless you pass `--reset`.

## Walkthrough (about 75 seconds)

1. **Air-gap.** Click *Cloud allowed* in the header so it switches to *Air-gapped*. Cloud providers are now blocked.
2. **The bug.** Open `pricing.py`.
3. **Goal.** In the agent panel, enter: `Fix the 10% discount bug in pricing.py and prove it with the tests`. The agent drafts a four-step plan.
4. **Read-only step.** Run `search_codebase` with `{"query": "apply_discount"}`. It runs without asking.
5. **Approval gate.** Run `edit_file`:
   ```json
   {"path": "pricing.py",
    "target": "    return price_cents - percent\n",
    "replacement": "    return round(price_cents * (100 - percent) / 100)\n"}
   ```
   The agent pauses and shows the exact edit. Click **Allow**.
6. **Diff.** Open the *Changes* view and click `pricing.py` to see the git diff.
7. **Tests.** Run `run_command` with `{"command": "python3 -m unittest -v"}`, then approve it. All 3 tests pass.
8. **Flight tape.** Open *Flight recorder*, pick the new tape and drag the scrubber through every decision. Use *Fork here* to branch a run from any step.
9. **Audit.** Open *Audit* and click **Verify chain**.
10. **Global.** Switch the language to العربية (right-to-left) and toggle the theme.
11. **Tier 2 Hardware Verification & Sealed Export.** Run hardware attestation checks directly via CLI or API:
    ```bash
    python cli.py tier2 status     # View live TPM 2.0, Dual-WORM, PIV, and 2-of-3 Recovery status
    python cli.py tier2 verify     # Run cryptographic proof verifications
    python cli.py tier2 demo       # Interactive walkthrough of all 4 Tier 2 gates
    python cli.py record anchor --out audit.anchor.json # Anchor head & publish Git note
    python cli.py record export --out audit.record.jsonl
    python cli.py record verify audit.record.jsonl --anchor audit.anchor.json # Detect tail truncation
    ```
    Or via the REST API:
    ```bash
    curl http://127.0.0.1:8000/v1/tier2/status
    curl -X POST http://127.0.0.1:8000/v1/audit/anchor
    curl -OJ http://127.0.0.1:8000/v1/audit/export?download=true
    ```
12. **Agent Manifests & Cost Metering.** Validate and sign manifests with strict budget guardrails:
    ```bash
    python cli.py agent validate docs/spec/examples/test-fixer.agent.json
    python cli.py agent sign docs/spec/examples/test-fixer.agent.json
    python cli.py agent verify docs/spec/examples/test-fixer.agent.json
    ```
13. **KStack, KBrain, KHub, KSpaces & KFlow Governance.** Inspect role skills, DLP fact memory, team spaces, and DAG proofs:
    ```bash
    python cli.py skill list           # List pinned role skills (plan, review, qa, security)
    python cli.py brain query          # Query scope-governed knowledge facts
    python cli.py hub list            # Discover imported third-party skills and prompt rules
    python cli.py space list          # List collaborative team workspaces and RBAC roles
    python cli.py flow run             # Execute deterministic DAG workflow with sealed proof packet
    ```
14. **Dual-Mode External Editor Sync.** Seamlessly open the seeded demo project in VS Code or Cursor:
    ```bash
    python cli.py sync editor                     # Inspect active watcher & debounce state
    python cli.py sync editor --open vscode       # Launch workspace directly in VS Code
    python cli.py sync editor --open cursor       # Launch workspace directly in Cursor
    ```
    Or click the **Open in VS Code** button in the top-right header of the Studio Monaco editor.

## Cleanup

```bash
rm -rf ~/keelway-demo
```
