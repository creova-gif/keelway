# Verify Feature: Formal Safety Verifier & Federated Edge-to-Cluster Mesh (`KEEL-SAFETY-024`)

1. Launch isolated `:7420/app`:
   `node .cursor/skills/verify-keelway/scripts/control-keelway.mjs launch --state-dir /tmp/keelway-verify-p17`
2. Switch to **Security** tab (`browser click --name "Security"`), `browser wait-for --text "Formal Safety State-Machine Verifier & Federated Edge Mesh"`.
3. Click **Verify State-Machine Safety** on the unguarded destructive scenario, verify `VIOLATION_FOUND` + counterexample path, then click **Inject P-10 Guard & Re-Verify** and verify `VERIFIED_SAFE` + `proof_sha256`.
4. Click **Dispatch Attested Edge-to-Cluster Handoff**, verify `ATTESTED_COMPLETE` + `edge_local` PII pinning + `cluster_burst` synthesis + `attestation_sha256`.
5. Verify CLI (`cli -- safety list --json`, `cli -- mesh handoffs --json`) and SQLite WAL tables (`safety_verifications`, `mesh_nodes`, `mesh_handoffs`), then `cleanup`.
