# Verify Feature: Typed Structured-Output Normalizer & Self-Healing Root-Causer (`KEEL-HEAL-023`)

1. Launch isolated `:7420/app`:
   `node .cursor/skills/verify-keelway/scripts/control-keelway.mjs launch --state-dir /tmp/keelway-verify-p16`
2. Switch to **Agents** tab (`browser click --name "Agents"`), `browser wait-for --text "Structured-Output Normalizer & Self-Healing Root-Causer"`.
3. Select `deepseek_opencore` or `anthropic` wire fixture, click **Normalize Content Blocks**, then click **Enforce JSON Schema Contract** and verify `REPAIRED_VALID` badge + `run_sha256`.
4. Select `schema_mismatch` (or `airgap_egress_blocked`) failure scenario, click **Diagnose Root Cause**, verify failure class + unified patch diff + `diagnosis_sha256`, then click **Apply Patch & Promote Golden Eval** and verify `VERIFIED_HEALED` + promoted Golden Eval `case_id`.
5. Verify CLI (`cli -- structured runs --json`, `cli -- heal list --json`) and SQLite WAL tables (`structured_output_runs`, `self_healing_diagnoses`, `platform_eval_dataset_cases`), then `cleanup`.
