# Feature Verification: Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation (`KEEL-DISTILL-026`)

## Scope
Verifies Phase 19 end-to-end across `:7420/app` (`Agents` workspace -> `ShadowCacheAndDistillationPanel`), Sovereign CLI (`keelway shadow` & `keelway distill`), and SQLite WAL persistence (`semantic_prompt_cache`, `shadow_distill_pairs`, `qlora_distill_datasets`).

## Cold Headless Chromium + CLI + SQLite WAL Flow
1. Launch isolated `:7420/app` instance via `node .cursor/skills/verify-keelway/scripts/control-keelway.mjs launch --state-dir /tmp/keelway-verify-p19`.
2. Switch to **Agents** workspace (`Agents`), scroll to **Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation**, run a Shadow Evaluation (`LOCAL_PARITY_READY` / `SHADOW_CAPTURED`) and re-run to trigger `CACHE_HIT` (`\$0.00` token spend), capturing `01-agents-shadow-cache-hit.png` + `.aria.txt`.
3. Switch to **QLoRA Distillation & Promotion Gate** tab, compile a `dpo_preference` dataset (`dataset_sha256`) and evaluate OpenCore Promotion Readiness (`PROMOTE_TO_OPENCORE` / `NEEDS_MORE_PAIRS`), capturing `02-agents-qlora-dataset-and-promotion.png` + `.aria.txt`.
4. Query CLI `keelway shadow stats --json` and `keelway distill datasets --json` against the same isolated `platform_runtime.db` and inspect SQLite WAL tables (`semantic_prompt_cache`, `shadow_distill_pairs`, `qlora_distill_datasets`) to verify zero unredacted secrets and cryptographic SHA-256 digests.
5. Shut down cleanly via `control-keelway.mjs cleanup`.
