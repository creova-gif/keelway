# Package C fail-closed boundary

This note records the compatibility, threat, and rollback behavior of the
foundation-repair package C changes. It is not a certification. Shield and
Milo review the final SHA separately.

## What changed

Governance create, enqueue, cancel, approval, quorum, pull-request, and
deployment routes refuse a missing or invalid bearer before they construct a
run, append a job, or mutate a repository. Runner poll, on both the governance
server and Studio, accepts a token only after an explicit enrollment HMAC
check. A token that merely has the shape `runner:org:stamp:forged` does not
dequeue a job.

The governance browser origin gate no longer sends `Access-Control-Allow-Origin: *`
with credentials. A missing `Origin` (CLI and TestClient) still passes the
origin gate. Loopback origins pass only when they match the request `Host`.
Any other origin is denied with 403 before the route runs, unless it is listed
in `KEELWAY_GOVERNANCE_ALLOWED_ORIGINS`. The value `*` in that list is ignored.

`run_command` without `command_runner`, and `POST /v1/terminal/exec`, return
unavailable and do not start a host shell. Resuming an approval does not
change that. Manifest runs that already call `Sandbox.require_verified()` keep
the macOS seatbelt path. This change does not add a Linux sandbox and does not
add a flag that turns the host shell back on. A test may install an explicit
fake `command_runner`; that double is not OS verification.

`ApprovalService`, `TwoHumanQuorumService`, `BillingWebhookHandler`,
`EntitlementManager`, `GlobalPaymentBroker`, and `GitHubAppWebhookHandler`
do not produce a runnable approval, grant, intent, or webhook result from a
source-default secret. Passing that same default explicitly is also refused.
Import and construction still succeed so existing processes can start. The
refused operation returns a failure or raises `InsecureDefaultConfiguration`.

## Supported local boundary

Set these only to values that are not the published source defaults:

- `KEELWAY_API_TOKEN` or `KEELWAY_GOVERNANCE_TOKEN` for governance mutations
  when authentication is required. The Studio launch token is also accepted
  when `core` is installed. The loopback dashboard receives that token in the
  page; a non-loopback response does not.
- `KEELWAY_APPROVAL_SIGNING_KEY` and `KEELWAY_QUORUM_SIGNING_KEY` before a
  governed run that must record an approval.
- `KEELWAY_GITHUB_WEBHOOK_SECRET` before the governance process is imported,
  if GitHub webhooks must verify.
- `enroll_runner(runner_id, org_id, secret)` for a runner that must poll.
- An explicit constructor argument for payment, billing, and entitlement
  callers that need those operations.

`settings.auth_required` remains the existing Studio flag. Package C does not
add another switch that disables these refusals.

## Rollback

Revert the package C commit. No migration and no secret rotation is required.
Source-default material was not rotated; it was refused. Restoring the commit
restores the previous host-shell and open governance behavior.

## Limits

Profile A on Linux does not prove macOS seatbelt. A passing hermetic run does
not mean a live model or a verified OS sandbox was exercised. Runner
acknowledgement still has no token of its own. Billing entitlements keep the
published default in source so older certificates can be recognized as
non-runnable rather than silently re-signed.
