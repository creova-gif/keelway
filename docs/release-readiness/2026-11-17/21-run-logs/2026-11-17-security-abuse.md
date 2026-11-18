# Security abuse run — 2026-11-17

Instance: uvicorn core.main:app :7422, AUTH_REQUIRED=true, KEELWAY_API_TOKEN=<pinned test owner token>
Second principal: auditor token `abuse-auditor` id=55b56a08 (minted via `keelway token create`)

| Test | Result |
|---|---|
| GET /v1/workspaces no token | 401 |
| GET /v1/workspaces bogus bearer | 401 |
| GET /v1/workspaces owner | 200 |
| POST /v1/tokens as auditor (role=owner) | 403 |
| POST /v1/workspaces/{id}/activate as auditor | 403 lacks execute_agent |
| DELETE /v1/workspaces/{id} as auditor | 403 lacks approve_tier3 |
| GET /v1/files/content?path=../../etc/passwd | 403 traversal |
| ...?path=/etc/passwd | 403 traversal |
| ...?path=..%2f..%2fetc%2fpasswd | 403 traversal |
| POST /v1/files/save path=../evil.txt | 403 traversal |
| GET /v1/files/content?path=.env | 404 not found |
| POST /v1/terminal/exec {"command":"id"} | 503 fail-closed |
| GET /v1/messaging/whatsapp/webhook no sig | 403 verification failed |
| GET /v1/models/local, /v1/entitlements/status, /v1/sync/status | 200, no secrets in body |
| POST /v1/agent/approve/{fake} ×2 | 400 consistent (explicit boolean required) |
| CORS header | none (no wildcard) |

Notes: auditor token can read workspace list (view permission — consistent with auditor role).
Enqueue of `x; id` prompt stores text only; no execution path taken (runner requires isolation).
