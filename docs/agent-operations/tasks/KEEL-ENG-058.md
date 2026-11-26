# KEEL-ENG-058 — CI installs the locked dependency set (requirements.lock)

## Objective

Close the CI/lock drift: test jobs previously installed
`pip install -e ".[dev]"` against floating `>=` ranges, so CI tested
whatever PyPI resolved that day while `requirements.lock` — the
canonical, hash-verified pin set — was never installed anywhere.

## Findings

1. **Lock not load-bearing**: `requirements.lock` (uv-compiled, hashed,
   `--extra dev --extra postgres`) pinned fastapi 0.163.1 / pydantic
   2.14.3 while CI's floating install landed on fastapi 0.165.0 /
   pydantic 2.14.4 — the exact drift that surfaced the
   UnsupportedFieldAttributeWarning flood (KEEL-ENG-057). CI was
   proving green on a dep set the lock had never described.
2. **Freshness gate was a silent no-op in CI**: `check_python_lock.sh`
   exits 0 ("uv not found on PATH; skipping") when `uv` is absent, and
   CI's `pip install -e ".[dev]"` never provided it — so the gate has
   never executed in CI.
3. **Pin-preserving semantics**: `uv pip compile` (the canonical
   command in check_python_lock.sh and the lock header) preserves
   existing pins — the lock only moves on `--upgrade` or new declared
   deps. So the lock was "fresh" per the gate yet 8 releases behind
   PyPI. This is correct lock behavior: upgrades must be deliberate,
   and this task makes one.
4. **Cross-version safe**: the lock contains zero
   `python_version`-conditional entries; the upgraded pins match the
   resolution both CI legs (3.11, 3.14) already proved green, so the
   same lock installs on both.

## Shipped

- `requirements.lock` upgraded deliberately
  (`uv pip compile ... --generate-hashes --upgrade`) to the exact
  resolution CI's floating installs had been proving green —
  annotated-doc 0.0.7, certifi 2026.11.20, fastapi 0.165.0,
  packaging 26.4, pydantic 2.14.4, pydantic-core 2.50.5,
  pyyaml 6.0.4, ruff 0.17.6 — zero regression risk vs prior CI env
- `ci.yml` test job: `pip install -r requirements.lock` (hash-verified)
  + `pip install -e . --no-deps` (editable install for `keelway`
  console-script / `importlib.metadata` users); `uv==0.11.7` installed
  and pinned so `check_python_lock.sh` executes deterministically
  instead of silently skipping; pip `cache-dependency-path` gains
  `requirements.lock`
- `release-gate-macos.yml`: same lock install — release verification
  must not drift from what PR CI proved

## What this does NOT change

- `pip install -e ".[dev]"` remains the documented local dev flow
  (`requirements.txt` stub, docs unchanged)
- The wheel job's isolated-install verification is untouched — it
  validates the built artifact against floating deps, a legitimate
  "what users get today" canary
- `check_python_lock.sh` itself is unchanged — it already did the
  right thing when `uv` is present; it now always is in CI

## Operational consequence

When a PyPI release drifts the resolution, nothing in CI changes —
the lock only moves when someone regenerates with `--upgrade`
(deliberate diff, reviewed like code). The lock-freshness gate
continues to catch declared-dep changes to pyproject.toml. Upstream
canary signal now lives in the wheel job and in deliberate upgrades.

## Verification

- `uv pip compile ... --upgrade -o requirements.lock`: resolved 38
  packages; pins now match the floating resolution both CI legs proved
- `grep -c python_version requirements.lock` → 0 (no version-conditional
  entries; single lock valid on 3.11 and 3.14)
- `python3 -c "yaml.safe_load(...)"` both workflows parse
- Expected CI delta: test jobs install the identical pinned set every
  run; mid-flight dep changes impossible
