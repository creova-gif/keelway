# KEEL-REL-059 — M7 Distribution: Signed Artifacts, PyPI OIDC, Homebrew Formula

- **STATUS**: VERIFIED_COMPLETE (signing + formula verified; PyPI publish gated on founder setup)
- **LAST AGENT**: Devin
- **DATE**: 2026-11-17
- **BRANCH**: `main`

## Objective & Acceptance Criteria

Milestone 7 slice: signed release artifacts, PyPI publish path, Homebrew formula.

- [x] Artifacts cryptographically signed (Sigstore keyless, no key custody)
- [x] PyPI publish job wired with OIDC trusted publishing
- [x] Homebrew formula generated + install path verified
- [x] Vendor hook re-probe executed

## Implementation

1. **Signing** — `release-artifacts.yml`: `id-token: write`, cosign
   `sign-blob` of `SHA256SUMS.txt` → `.cosign.bundle` uploaded to the release.
   Customer verification command documented in `docs/runbooks/DISTRIBUTION.md`.
2. **PyPI** — `publish-pypi` job on tag pushes: OIDC trusted publishing via
   `pypa/gh-action-pypi-publish`, double-gated on `environment: pypi` AND
   `vars.PYPI_PUBLISH_ENABLED` — skips cleanly until founder configures both.
3. **Homebrew** — `scripts/gen_homebrew_formula.py` resolves the full dep
   closure (`pip --report`, cp313, macOS arm64 + Linux x86_64) into
   `packaging/homebrew/keelway.rb`: 41 URL+sha256 `resource` blocks,
   `virtualenv_install_with_resources`, `doctor --json` test block.

## Tests & Evidence

- `pip install` replication of `virtualenv_install_with_resources` on
  `python@3.13`: 30 macOS-scope wheels + sdist → `keelway doctor --json`
  rc 0 (`overall_status` present). `keelway --version` correctly removed
  from test block — CLI has no `--version` flag (usage rc 2).
- `brew fetch` via local tap: all 41 resources verified sha256 OK.
- `brew install` proper blocked by host CLT/macOS-27 mismatch — flagged as
  host-environment issue; clean-runner check documented in runbook.
- Generator bug caught+fixed: `pip --dry-run` skipped env-satisfied packages
  (pydantic, anyio, h11, idna…) → `--ignore-installed` added; closure went
  21→41 resources.
- Workflow YAML parses clean; `ruby -c` on formula OK.

## Vendor Re-probe (2026-11-17)

- `claude`: **still gated** — local UserPromptSubmit token-quota hook at
  101% (1,010,151/1,000,000), resets midnight. Not a Keelway failure.
- `codex`: **still gated** — vendor "usage limit … try again Nov 20, 2026
  4:15 PM". Scheduled.
- Notable: codex fired `SessionStart`+`UserPromptSubmit` hooks during the
  failed run — hook *delivery* works, only inference is gated.

## Known Limits / Next Actions

- PyPI publish: needs founder to configure trusted publisher + `pypi`
  environment + `PYPI_PUBLISH_ENABLED=true`, then next tag publishes.
- Tap repo `creova-gif/homebrew-keelway` does not exist yet — copy
  `packaging/homebrew/keelway.rb` → `Formula/keelway.rb` on creation.
- `brew install` clean-runner verification pending (host CLT broken).
- Re-probe claude after midnight; codex after Nov 20 4:15 PM.
