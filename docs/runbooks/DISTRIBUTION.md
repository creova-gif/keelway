# Keelway Distribution & Signed Artifacts

> Channels, signing, and verification for Keelway releases.
> Workflow: `.github/workflows/release-artifacts.yml` (tag `v*` or manual).

## Release Artifacts (per tag)

| Artifact | Purpose |
|---|---|
| `keelway-<ver>-py3-none-any.whl` | Python wheel (`pip install`) |
| `keelway-<ver>.tar.gz` | Source distribution |
| `keelway-sbom.cdx.json` | CycloneDX 1.5 SBOM, self-verifying via `SBOMVerifier` |
| `SHA256SUMS.txt` | SHA-256 checksums for all artifacts |
| `SHA256SUMS.txt.cosign.bundle` | Sigstore keyless signature bundle (GitHub OIDC) |

## Verifying a Release (customer-facing)

```bash
cosign verify-blob \
  --bundle SHA256SUMS.txt.cosign.bundle \
  --certificate-identity-regexp 'https://github.com/creova-gif/keelway/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  SHA256SUMS.txt
sha256sum -c SHA256SUMS.txt
```

Keyless signing binds the checksums to this repository's GitHub Actions
identity — no private key to manage or leak.

## PyPI (`pip install keelway`)

The `build-and-publish-pypi` job in `.github/workflows/release-pypi.yml`
uses OIDC trusted publishing — no long-lived token. One-time founder setup:

1. **pypi.org** → create project `keelway` → add trusted publisher:
   repo `creova-gif/keelway`, workflow `release-pypi.yml`, environment `pypi`.
2. **GitHub** → create environment `pypi` → set repo variable
   `PYPI_PUBLISH_ENABLED=true`.

Until both are set the job skips — it never uploads without them.

## Homebrew (`brew install keelway`)

`packaging/homebrew/keelway.rb` is generated — do not hand-edit:

```bash
python scripts/gen_homebrew_formula.py \
  --version <ver> \
  --sdist-url <release-or-pypi-sdist-url> \
  --sdist-sha256 <sha256> \
  --out packaging/homebrew/keelway.rb
```

- Resolves the **full** dependency closure via `pip --report` pinned to
  cp313 wheels for macOS arm64 + Linux x86_64 (`on_macos`/`on_linux` splits).
- 41 resource blocks, each URL + sha256 — deterministic, air-gap-friendly.
- Publish path: create tap `creova-gif/homebrew-keelway`, copy the formula
  into `Formula/keelway.rb`, tag a release.

### Verified (2026-11-17)

- `brew fetch` of the formula: all 41 resources download + sha256-verify.
- Install replication (`virtualenv_install_with_resources` equivalent) on
  `python@3.13`: `keelway doctor --json` → rc 0.
- `brew install` proper is blocked on this host by a stale CLT/macOS-27
  mismatch (host environment, not the formula) — verify on a clean runner.
