# Verify Feature: Cyclic KFlow Sub-Graphs & Cost/Privacy Autopilot (`KEEL-KFLOW-022`)

1. Launch isolated `:7420/app`:
   `node .cursor/skills/verify-keelway/scripts/control-keelway.mjs launch --state-dir /tmp/keelway-verify-p15`
2. Switch to **Automation** tab (`browser click --name "Automation"`), wait for `Bounded Cyclic KFlow & Cost/Privacy Autopilot`.
3. Select `airgap_strict` privacy policy, click **Simulate Pre-Run Blast & Autopilot**, and verify `simulation_sha256` + local OpenCore checkpoint rewrites (`keelway-core:7b`, \$0.00 egress).
4. Click **Execute Reflection Loop**, verify `CONVERGED` badge, per-iteration critic progression, `map_reduce` shard count, and `run_sha256`; then click **Trigger Saga Compensation** and verify `COMPENSATED` rollback log.
5. Verify CLI (`cli -- kflow-cyclic runs --json`, `cli -- autopilot list --json`) and SQLite WAL tables (`kflow_cyclic_runs`, `kflow_autopilot_simulations`), then `cleanup`.
