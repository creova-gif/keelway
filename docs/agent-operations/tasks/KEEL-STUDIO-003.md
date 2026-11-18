# TASK: KEEL-STUDIO-003 — Manifest Inspection Panel in Web Developer Studio

## 1. METADATA
- **TASK ID**: KEEL-STUDIO-003
- **CATEGORY**: UI / STUDIO
- **CREATOR**: Keelway Platform Architecture Team
- **ASSIGNED AGENT**: Google Antigravity (Studio Manifest Inspector Lead)
- **STATUS**: READY_FOR_REVIEW
- **TARGET BRANCH**: `feature/KEEL-STUDIO-003-manifest-view` (verified on `main` @ `5b2fbc3`)
- **BASE COMMIT**: `5b2fbc3`

---

## 2. OBJECTIVE & MOTIVATION
Provide developers and security operators inside **Keelway Web Developer Studio** (`/studio`) with a first-class, air-gap-safe **Agent Manifest Inspector** (`keelway.agent/v1`). Operators need unified visibility into both SQLite-registered `AgentManifestRecord` specs and workspace `*.agent.json` files—covering HMAC-SHA256 cryptographic signature verification, registry kill-switch state, autonomy and sandbox tiers, scoped tool/path/command permissions, token-metered USD run budgets, fail-closed posture warnings, canonical JSON, and live custom manifest JSON validation without mutating disk or auto-creating signing keys.

---

## 3. ACCEPTANCE CRITERIA
- [x] **Criterion 1**: `GET /v1/studio/manifests` discovers and merges SQLite `AgentManifestRecord` entries (`list_registered_manifests(db)`) and bounded workspace `*.agent.json` files (`agents/`, `docs/spec/examples/`, `.keelway/manifests/`) while ignoring `.git`, `node_modules`, and symlinks.
- [x] **Criterion 2**: `GET /v1/studio/manifests` and `POST /v1/studio/manifests/inspect` verify HMAC-SHA256 signatures (`verified`, `unsigned`, `invalid_signature`, `key_missing`), return normalized `governance_summary` and actionable `security_warnings`, and **never** create `.keelway/agent_signing.key` or leak key material.
- [x] **Criterion 3**: `GET /v1/studio/status` includes additive `"manifests_count"` telemetry without breaking existing Studio API consumers.
- [x] **Criterion 4**: Web Developer Studio (`core/studio/index.html` & `core/studio/assets/studio.js`) provides a `Manifests` navigation rail view (`#rail-manifests-btn`), `#studio-manifests-panel` inspector master-detail UI, and a live `Validate Custom Manifest JSON` drawer under strict `script-src 'self'` CSP (zero external CDNs, zero inline event handlers, `textContent` rendering only).
- [x] **Criterion 5**: Automated tests written and passing in `tests/test_studio_manifest_panel.py`, zero regressions across `tests/test_studio.py`, `tests/test_studio_api.py`, `tests/test_proof_strip_ux.py`, `tests/test_slice2_ide_usability_e2e.py`, and `node --check core/studio/assets/studio.js`.
- [x] **Criterion 6**: Zero security or privacy regressions; secret signing key bytes never appear in API payloads or error messages.

---

## 4. AFFECTED FILES & COMPONENTS
- **Primary Files**:
  - `core/api/studio.py`: Added non-mutating signing key reader, signature inspector, governance summary builder, security posture analyzer, bounded workspace `*.agent.json` discovery, `manifests_count` in `GET /v1/studio/status`, `GET /v1/studio/manifests`, and `POST /v1/studio/manifests/inspect`.
  - `core/studio/index.html`: Added `#rail-manifests-btn` navigation button, `#sec-manifests` / `#studio-manifests-panel` master-detail inspection panel, `#manifest-validator-drawer` custom JSON validator, `#registry-open-inspector-btn` shortcut, and `#sb-manifests` status bar telemetry.
  - `core/studio/assets/studio.js`: Added Manifest Inspector state, badge formatters (`VERIFIED`/`UNSIGNED`/`INVALID`/`KEY MISSING`, `ENABLED`/`DISABLED`, routing policy), manifest list filtering/selection, detail rendering, kill-switch toggling, live custom JSON inspection, Command Palette commands, and `Alt+7` navigation shortcut.
- **Test Files**:
  - `tests/test_studio_manifest_panel.py`: Comprehensive API, cryptographic signature state, secret non-leakage, schema rejection, security posture warning, HTML landmark/CSP, and Node JS syntax & helper verification tests.
- **Documentation**:
  - `docs/agent-operations/tasks/KEEL-STUDIO-003.md`: Task specification and handoff record.

---

## 5. SECURITY & PRIVACY CONSIDERATIONS
- **Privacy Fail-Closed verification required?**: Yes — Studio assets remain 100% self-hosted (`default-src 'self'; script-src 'self'`) with zero external CDN dependencies and zero inline JS handlers in the Manifest Inspector panel.
- **Credential handling / secret redaction involved?**: Yes — `.keelway/agent_signing.key` is read strictly in read-only mode when already present on disk (`is_file()` and not symlink), never auto-created on status/inspection calls, and raw key hex/bytes are verified by test never to leak in HTTP responses.
- **Autonomy Tier Level**: Tier 2 Governed (Registry kill-switch mutations remain gated behind `Permission.APPROVE_TIER3` on `/v1/agents/registry/{name}/{version}/toggle`; inspection endpoints are strictly read-only).

---

## 6. VALIDATION & TEST PLAN
```bash
cd keelway
PYTHONPATH=. ../kora-ai.nosync/.venv/bin/pytest tests/test_studio.py tests/test_studio_manifest_panel.py -v
PYTHONPATH=. ../kora-ai.nosync/.venv/bin/pytest tests/test_studio_api.py tests/test_proof_strip_ux.py tests/test_slice2_ide_usability_e2e.py -v
node --check core/studio/assets/studio.js
```

---

## 7. EXECUTION LOG & AGENT HANDOFF HISTORY

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-STUDIO-003
- **TASK TITLE**: Manifest Inspection Panel in Web Developer Studio
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Antigravity
- **DATE**: 2026-11-13
- **BRANCH**: `main` (parallel multi-agent workspace; target feature branch `feature/KEEL-STUDIO-003-manifest-view`)
- **HEAD COMMIT**: `5b2fbc3` (with clean uncommitted task changes on owned files)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] `GET /v1/studio/manifests` unified discovery of SQLite registry + bounded workspace `*.agent.json` files (verified in `test_studio_manifests_discovers_workspace_and_registry_without_creating_signing_key`)
- [x] Non-mutating HMAC-SHA256 signature verification (`verified`, `unsigned`, `invalid_signature`, `key_missing`) with zero secret key leakage (verified in `test_studio_manifest_signature_states_and_zero_secret_key_leakage`)
- [x] `POST /v1/studio/manifests/inspect` schema validation (extra fields, `../` traversal, `.keelway/` protected path, `;` shell metacharacters, malformed JSON) & security posture warnings (`network="allowlist"`, autonomous mutation) (verified in `test_studio_inspect_manifest_rejects_invalid_schemas_and_flags_security_warnings`)
- [x] Additive `manifests_count` in `GET /v1/studio/status`
- [x] Web Developer Studio `Manifests` view (`#studio-manifests-panel`) and live `Validate Custom Manifest JSON` validator respecting strict air-gap CSP (verified in `test_studio_html_has_manifest_inspector_landmarks_and_strict_csp` & `test_studio_js_syntax_and_manifest_badge_helpers`)

#### WORK COMPLETED & FILES MODIFIED
- `core/api/studio.py`: Implemented `_load_existing_signing_key`, `_inspect_signature`, `_governance_summary`, `_security_warnings`, `_discover_workspace_manifest_files`, `_inspect_manifest_payload`, `GET /v1/studio/manifests`, `POST /v1/studio/manifests/inspect`, and `manifests_count` in `GET /v1/studio/status`.
- `core/studio/index.html`: Added `Manifests` rail navigation button, `#sec-manifests` / `#studio-manifests-panel` inspector layout, `#manifest-validator-drawer` custom JSON validator, `#registry-open-inspector-btn`, and `#sb-manifests` status bar indicator.
- `core/studio/assets/studio.js`: Implemented `loadStudioManifests`, `renderManifestsList`, `selectStudioManifest`, `renderSelectedManifest`, `inspectCustomManifestInStudio`, `renderCustomManifestInspectResult`, `loadSampleManifestInStudio`, badge helpers, Command Palette shortcuts, and `Alt+7` navigation. Also updated `loadManifestRegistry` to support `{ manifests: [...] }` responses and pass `{ enabled }` on kill-switch toggle.
- `tests/test_studio_manifest_panel.py`: Added 5 end-to-end API, security-posture, HTML/CSP, and Node JS tests.
- `docs/agent-operations/tasks/KEEL-STUDIO-003.md`: Created complete task specification and handoff record.

#### TESTS EXECUTED & EVIDENCE
- `PYTHONPATH=. ../kora-ai.nosync/.venv/bin/pytest tests/test_studio.py tests/test_studio_manifest_panel.py -v`: `6 passed, 1 warning in 0.51s`
- `PYTHONPATH=. ../kora-ai.nosync/.venv/bin/pytest tests/test_studio.py tests/test_studio_manifest_panel.py tests/test_studio_api.py tests/test_proof_strip_ux.py tests/test_slice2_ide_usability_e2e.py -v`: `29 passed, 1 warning in 12.27s`
- `PYTHONPATH=. ../kora-ai.nosync/.venv/bin/pytest tests/test_runtime_truth_package_b.py -k "studio or package_b_sources or proof_strip or ledger" -v`: `6 passed, 2 deselected in 0.63s`
- `node --check core/studio/assets/studio.js`: `exit code 0`

#### KNOWN RISKS & BLOCKERS
- None for `KEEL-STUDIO-003`. Manifest signature verification currently validates workspace HMAC-SHA256 keys (`keelway.agent/v1`); asymmetric Ed25519 registry verification remains a planned platform enhancement noted in `core/agents/manifest.py`.

#### NEXT RECOMMENDED ACTION
- Coordinator / Release Lead can update `docs/agent-operations/ACTIVE_TASKS.md` to mark `KEEL-STUDIO-003` as `READY_FOR_REVIEW` / `VERIFIED_COMPLETE` and include the 5 owned files in the integration commit.
