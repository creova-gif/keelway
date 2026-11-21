# KEEL-APP-069 — P-10 card + Overlays conformance vs Paper 18.1 (`2O0-0`) / 18.3 (`2RP-0`)

## Status
READY_FOR_REVIEW — conformance verified, no code delta required.

## Audit outcome

**P-10 approval card (18.1):** shipped `P10ApprovalCard` exceeds the artboard on every element —
loud pending grammar (`border-s-ochre`), scope/policy badges (`domainPolicyCode`, `Human-only`),
preview box (the artboard's "Inspect payload"), edit escalation, click-only Variant-C gates,
deny reason to ledger, governance footer. Artboard `expires` maps to `expiresAtEpoch` on standing
rules — surfaced in Permissions panel. Forcing visual parity would strip honest detail; code wins.

**Onboarding modal (18.3):** shipped `OnboardingModal` exceeds — real `/v1/system/doctor` checks
with remediation, workspace binding, provenance badges, `Step 1 / 2` counter, skip/continue.

**Command palette (18.3):** shipped `CommandPalette` conforms — `needs_approval` tasks rank first
(priority 0, jump-to-gate), footer carries "Approvals are never run from here" + Esc hint,
mode prefixes (> # @ /), kind badges. Artboard's "Approve pending P-10 gate" = task entry →
`onJumpToApprovalHeading`.

## Next
KEEL-APP-070: 18.4 views + 18.5 drawers conformance; then 18.2 Billing (blocked on 4-vs-5 tier
decision) and page-19 new surfaces (composer deep-dive, switcher+inbox, auth/About).
