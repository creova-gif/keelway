# Keelway — gstack Engineering Review & Delivery Guide

> **Scope**: Using gstack specialist workflows within Keelway's development lifecycle.  
> **Applicable Hosts**: Claude Code, Cursor, Codex CLI, or any agent host with gstack installed.

---

## 1. The 7-Stage gstack Delivery Sequence

Where gstack is installed, substantial features and architectural changes should progress through the structured sequence:

```
[ 1. Think ]   --> /office-hours        (Product framing, 10-star experience, edge cases)
      |
[ 2. Plan ]    --> /autoplan            (CEO review -> Design review -> Eng review)
      |            /plan-eng-review     (Lock data flow, error invariants, privacy gates)
      |
[ 3. Build ]   --> Universal Protocol   (Implement minimal diff, write automated tests)
      |
[ 4. Review ]  --> /review              (Pre-landing review: find prod breakages, gate integrity)
      |
[ 5. QA ]      --> /qa                  (Reproduce edge cases, verify streaming & APIs)
      |
[ 6. Security] --> /cso                 (Static/runtime security scans, secret leak checks)
      |
[ 7. Ship ]    --> /ship                (Test verification, PR creation - with approval)
```

---

## 2. Command Mapping & Repository Quality Equivalents

If gstack is **NOT** installed on your agent host, execute the equivalent repository-native verification procedures:

| gstack Skill | Primary Objective | Keelway Repository-Native Equivalent |
|---|---|---|
| `/office-hours` | Reframes product idea before writing code | Review `docs/product/PRODUCT_STRATEGY.md` and acceptance criteria |
| `/plan-eng-review` | Locks architecture, failure modes, tests | Author or update ADR in `docs/decisions/` and review against `AGENTS.md` |
| `/review` | Pre-commit inspection for bugs and regressions | Self-review diff against `docs/engineering/QUALITY_GATES.md` |
| `/qa` | Functional API, CLI, and streaming testing | Run `pytest tests/ -v` and test with `httpx` / `curl` |
| `/cso` | Static code & container vulnerability scan | Run `core.security.redact` tests and dependency audit |
| `/ship` | Gate verification and PR preparation | Run `bash scripts/verify_engineering_gates.sh` and push task branch |

---

## 3. Strict Safety & Approval Boundaries

1. **No Unapproved Deployment**: Never invoke `/ship` or push to `main` without explicit human authorization.
2. **Runtime Independence**: Keelway never relies on gstack as a production runtime dependency. gstack is purely a developer experience and review harness.
3. **No Code Duplication**: Do not duplicate gstack skill files into Keelway's repository.
