# Verify Feature: Universal Coding-Agent Co-Harness & Parallel Worktree CI Gate (`KEEL-HARNESS-025`)

1. Launch isolated `:7420/app`:
   `node .cursor/skills/verify-keelway/scripts/control-keelway.mjs launch --state-dir /tmp/keelway-verify-p18`
2. Switch to **Operations** tab (`browser click --name "Operations"`), `browser wait-for --text "Universal Coding-Agent Co-Harness & Worktree CI Gate"`.
3. Click **Intercept Tool Call** on the sensitive mutation preset (`git push origin main`), verify `HOLD_TICKET` + pending single-use ticket ID, then click **Approve & Replay Single-Use Ticket** and verify `ALLOW_WITH_TICKET`.
4. Click **Evaluate Worktree CI Gate**, verify `PASS` + `keelway-core:7b` winner + `$0.048` cost saved + `gate_sha256`.
5. Verify CLI (`cli.py harness tickets --json`, `cli.py ci-gate runs --json`) and SQLite WAL tables (`harness_interceptions`, `harness_approval_tickets`, `worktree_ci_gate_runs`), then `cleanup`.
