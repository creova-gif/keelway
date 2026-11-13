# `@keelway/sdk`

Official zero-dependency TypeScript & JavaScript SDK for the **Keelway Unified Hybrid AI Platform**.

- **Zero Runtime Dependencies**: Built strictly on Web Standard `fetch`, `ReadableStream`, `TextDecoder`, and `AbortSignal`. Runs cleanly in Node 20+, Bun, Deno, Cloudflare Workers, and modern browsers.
- **Unified Hybrid Inference**: Seamless switching between sovereign OpenCore checkpoints (`keelway-core:7b`, `keelway-nano:1.5b`) and frontier cloud providers (`gpt-4o`, `claude-3-7-sonnet`, `gemini-2.5-pro`).
- **Privacy Fail-Closed & Typed Errors**: Deterministic HTTP error mapping (`AirGapEgressError`, `BudgetExceededError`, `QuorumRequiredError`, `PolicyViolationError`, `RateLimitExceededError`).

## Quickstart

```ts
import { KeelwayClient, AirGapEgressError } from "@keelway/sdk";

const client = new KeelwayClient({
  baseUrl: "http://127.0.0.1:7420",
  apiKey: process.env.KEELWAY_API_KEY, // kw_live_*
  timeoutMs: 30_000,
});

// 1. Discover Open-Weight & Frontier models
const catalog = await client.models.list({ category: "open_weight" });

// 2. Explain 4D routing provenance without spending tokens
const route = await client.routing.explain({
  messages: "Summarize regulated payroll records",
  privacy_level: "private",
});

// 3. Stream chat completions across SSE chunks
for await (const chunk of client.chat.completions.stream({
  model: "keelway-core:7b",
  messages: [{ role: "user", content: "Write a zero-egress health check" }],
  privacy_level: "private",
})) {
  process.stdout.write(chunk.choices[0]?.delta?.content ?? "");
}

// 4. Stateful /v1/responses chaining with speculative decoding
const turn1 = await client.responses.create({
  input: "Outline a sovereign deployment topology.",
  privacy_level: "private",
  speculative: true,
});
const turn2 = await client.responses.create({
  input: "Add multi-tenant spend cap guardrails.",
  previous_response_id: turn1.id,
  privacy_level: "private",
});
```

## Surface Coverage

| Namespace | Methods | Endpoints |
|-----------|---------|-----------|
| `client.models` | `list(params?)` | `GET /v1/models` |
| `client.usage` | `get()` | `GET /v1/usage` |
| `client.chat.completions` | `create(req)`, `stream(req)` | `POST /v1/chat/completions` |
| `client.responses` | `create(req)`, `get(id)`, `stream(req)` | `POST /v1/responses`, `GET /v1/responses/:id` |
| `client.routing` | `explain(req)`, `decisions(params?)` | `POST /v1/routing/explain`, `GET /v1/routing/decisions` |
| `client.opencore` | `status()`, `weights()`, `compileModelfile(req)`, `adapters()` | `/v1/opencore/*` |
| `client.governance` | `upsertPolicy(policy)`, `getPolicy(id)`, `issueKey(req)`, `verifyAudit()` | `/v1/governance/*` |
| `client.swarm` | `evaluate(req)` | `POST /v1/eval/swarm` |

## Typed Error Hierarchy

| HTTP Status | Condition | Error Class | Code |
|-------------|-----------|-------------|------|
| `401` | Invalid / missing `kw_live_*` bearer token | `AuthenticationError` | `AUTHENTICATION_FAILED` |
| `402` | Daily or monthly tenant spend cap exceeded | `BudgetExceededError` | `BUDGET_EXCEEDED` |
| `403` | Message contains `"air-gap"` or `"egress"` | `AirGapEgressError` | `AIRGAP_EGRESS_BLOCKED` |
| `403` | Message contains `"quorum"` | `QuorumRequiredError` | `QUORUM_APPROVAL_PENDING` |
| `403` | General RBAC / scope denial | `PermissionDeniedError` | `PERMISSION_DENIED` |
| `404` | Missing task, response, model, or tenant | `TaskNotFoundError` | `TASK_NOT_FOUND` |
| `422` | Sovereign policy or schema violation | `PolicyViolationError` | `POLICY_VIOLATION` |
| `429` | Tenant RPM / TPM rate limit exceeded | `RateLimitExceededError` | `RATE_LIMIT_EXCEEDED` |
| Network / Abort | Unreachable daemon or `timeoutMs` exceeded | `ConnectionError` | `DAEMON_UNREACHABLE` |
