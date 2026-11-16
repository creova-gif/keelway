# KEEL-DOC-034 — Documentation Drift Sweep

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `DOCUMENTATION / DRIFT / PRODUCT-TRUTH` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-DOC-034-drift-sweep` |

## Objective
Correct documentation that drifted from verified repository state: version strings, nonexistent TLA+ specification references, and stale module paths — without rewriting legitimate historical records.

## Findings & Fixes
- **README.md version drift** — title, badge, intro, and capabilities header all said `v1.0.0` while `pyproject.toml` and `sdk/typescript/package.json` are `1.1.0`. Updated all to `v1.1.0`; TS SDK badge corrected; Go module has no version in `go.mod`, so its version label was removed rather than guessed.
- **Nonexistent TLA+ claims** — README claimed "formal TLA+ verified human governance" citing `specs/tla/P10HumanGate.tla`, and the repository tree listed `specs/tla/`. `git log --all` confirms `specs/` was **never committed**. Reworded to describe the implemented P-10 gate (`core/security/approval_rules.py`, `keelway/approvals/quorum.py`), removed the tree entry, and replaced "Formal TLA+ Verified" with "P-10 Human Approval Gate".
- **CHANGELOG.md historical claim** — the `1.1.0` entry records adding `specs/tla/P10HumanGate.tla`. Changelogs are historical records, so instead of deleting the claim an inline erratum was added noting the file was never committed and the gate is implemented/tested in code only.
- **Stale flight-recorder path** — `docs/audits/KEELWAY_CURRENT_STATE_2026-11.md` cited `core/flight/` and claimed a "doc conflict" on state-machine cardinality; `decision-precedence.md` §2 actually documents the canonical **16** states matching `TaskState`. Both corrected. The superseded `current-state-2026-11-05.md` audit got an erratum marker on its `core/flight/recorder.py` line pointing to `core/orchestration/flight_recorder.py` + `core/platform/flight_tape.py`.
- **Reviewed, intentionally unchanged** — `v1.0.0` references in `ACTIVE_TASKS.md`, task handoffs, and `ADR-0042` are legitimate historical/scheduled-version references, not drift.

## Acceptance Criteria
- [x] No README reference to `v1.0.0` as current version or to `specs/tla/`
- [x] No unqualified claim of formal TLA+ verification anywhere in user-facing docs
- [x] Current audit doc paths match actual module locations
- [x] Historical changelog/audit records preserved with errata rather than rewritten

## Files Modified
- `README.md`
- `CHANGELOG.md` (erratum only)
- `docs/audits/KEELWAY_CURRENT_STATE_2026-11.md`
- `docs/audits/current-state-2026-11-05.md` (erratum only)

## Tests Executed
- `pytest tests/test_website_facts.py -q`: **11 passed**
- Repo-wide grep: zero remaining `specs/tla`, `core/flight/` (outside errata), or stale `v1.0.0` current-version references

## Known Risks & Blockers
- None. Documentation-only change; no code paths touched.

## Next Recommended Action
Merge to `main`. Remaining backlog: VS Code extension webview palette migration (legacy slate), real OIDC federation or simulator relabeling, `core/config.py` `Field(default_factory=...)` fallback incompatibility, payment-processor integration when commerce is in scope.
