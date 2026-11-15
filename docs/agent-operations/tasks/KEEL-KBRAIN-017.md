# KEEL-KBRAIN-017 — Phase 10: Completing the 4-K Sovereign Architecture — KBrain Hybrid BM25/3-Gram Memory Graph, KHub Air-Gapped Skill Registry, Tarfile Symlink Hardening & Tri-SDK Parity

- **Status**: `VERIFIED_COMPLETE`
- **Assigned Agent**: Google Antigravity (3-Agent Parallel Wave: `10A`, `10B`, `10C` + Cold `verify-keelway` Proof + Live GitHub Actions CI)
- **Date**: 2026-11-15
- **Branch**: `main`

## Summary

Unified the remaining two pillars of Keelway's 4-K sovereign architecture (**KBrain** + **KHub**, joining **KFlow** + **KSpaces**) onto SQLite WAL (`platform_runtime.db`), `/v1/platform/kbrain/*` & `/v1/platform/khub/*`, Sovereign CLI (`kbrain`, `khub`), Tri-Language SDKs (`Python`, `TypeScript`, `Go`), and the 10-View Dev Tool (`Documentation` & `Marketplace` views), while hardening `core/khub/sync.py` against symlink/hardlink & sibling-prefix tar extraction attacks.

## Key Deliverables

1. **KBrain Hybrid Memory Graph, KHub Air-Gapped Registry & Tarfile Hardening (`core/platform/kbrain_khub.py`, `core/api/platform_kbrain_routes.py`, `core/cli_kbrain_khub.py`, `core/khub/sync.py`)**:
   - `SQLiteKBrainEngine`: Scope-hierarchic (`local_session <= project <= team <= org`) memory store with fail-closed DLP secret rejection (`SecretLeakDetectedError` -> `400`), automatic contradiction detection (`status="conflict"`), `runs:approve_p10` conflict resolution (`owner`/`operator` only), and deterministic Hybrid BM25 + character 3-gram cosine retrieval.
   - `SQLiteKHubRegistry`: Built-in `kstack` skill catalog digesting and live `.tar.gz` export/import roundtrip verification (`khub-airgap-mirror-v1`) persisted in `platform_khub_mirrors`.
   - `KHubBundlePacker.unpack_skill` & `KHubMirror.import_mirror`: Hardened with symlink/hardlink rejection, `Path.is_relative_to`, and Python 3.12+ `tarfile` `filter="data"`.
2. **Tri-SDK Parity & Website `/docs` Sync (`core/sdk/`, `sdk/typescript/`, `sdk/go/`, `website/src/components/docs/DocsHub.tsx`)**:
   - Added `record_kbrain_fact`, `search_kbrain_facts`, `resolve_kbrain_fact`, `list_khub_skills`, and `verify_khub_mirror` across Python, TypeScript (`@keelway/sdk`), and Go (`keelway-go`).
3. **Dev Tool (`:7420/app`) Panels & Full Workspace/RBAC Propagation (`dev-app/src/components/platform/`)**:
   - Mounted `KBrainMemoryGraphPanel.tsx` in `DocumentationWorkspaceView` and `KHubAirgapMirrorPanel.tsx` in `MarketplaceWorkspaceView`, wired live `workspaceId` & `activeRbacRole` propagation across `Documentation`, `Marketplace`, and `Operations` in `useUnifiedPlatformState.tsx`, and proved cold end-to-end with `control-keelway`.
