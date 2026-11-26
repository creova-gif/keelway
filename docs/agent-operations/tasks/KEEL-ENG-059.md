# KEEL-ENG-059 — CI dependency CVE gate (pip-audit on requirements.lock)

## Objective

Make dependency CVE posture continuous, not one-off: now that CI test
jobs install the canonical `requirements.lock` (KEEL-ENG-058), audit
that same pinned set on every PR.

## Shipped

New step in the `test` job (both 3.11/3.14 legs), after `ruff check`:

```yaml
- name: Dependency vulnerability audit (pip-audit on requirements.lock)
  run: |
    pip install pip-audit==2.10.1
    pip-audit -r requirements.lock --disable-pip
```

- Audits the **locked** pins — the exact set installed in the job —
  so a CVE in a pinned dep fails the gate deterministically.
- `pip-audit==2.10.1` pinned for deterministic CI (tool, not a runtime dep).
- Complements gitleaks (tracked-tree secrets) — this covers PyPI CVEs.

## Verification

- Local: `pip-audit -r requirements.lock --disable-pip` →
  "No known vulnerabilities found" on the upgraded lock
- JS surfaces already at 0 vulns (KEEL-WEB-049/-050: next 15.5.29,
  nested postcss override in both website/ and web-next/)
