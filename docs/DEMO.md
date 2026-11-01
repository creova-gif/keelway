# Demo: `kora demo`

One command seeds a sample project and opens the Studio on it. The demo has its own folder, git repo and SQLite database, so it never touches your real Kora data.

```bash
pip install -r requirements.txt
python cli.py demo                # ~/kora-demo, http://127.0.0.1:7420
python cli.py demo --reset        # wipe and re-seed
python cli.py demo --dir /tmp/kd --port 7431
```

The command prints a Studio URL with a launch token. Set `KORA_API_TOKEN` if you want a fixed token.

## What gets seeded

- `acme-checkout`: a tiny checkout service with a real bug. `apply_discount(1000, 10)` returns `990` instead of `900`. The `unittest` tests fail until it is fixed.
- Four tasks in different states, plus three project memories (integer cents, test command, release policy).
- One sealed flight tape (`task_demo_format_cents`) recorded by the real `AutonomousAgentLoop`: read, approved write, approved test run.

`kora demo` refuses to reuse a folder it did not create. Running it again reuses the seeded workspace unless you pass `--reset`.

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

## Cleanup

```bash
rm -rf ~/kora-demo
```
