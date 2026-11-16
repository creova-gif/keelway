# KEEL-SDK-009: Official Zero-Dependency Go Client SDK (`keelway-go`), Marketplace Commercial Settlement Ledger & Cross-SDK Cluster Parity

- **Status**: `VERIFIED_COMPLETE`
- **Category**: `SDK / MARKETPLACE / DX`
- **Completed**: `2026-11-14`
- **Branch**: `main`

## Delivered Scope
1. **Official Go Client SDK (`sdk/go/` — `github.com/keelway/keelway-go`)**:
   - Zero external runtime dependencies (`go.mod` stdlib-only), `Responses.Create` & chunk-boundary-safe `Responses.Stream` (`SSEStream`), `Routing.Explain`, `Platform` & `Cluster` namespaces, and typed governance error hierarchy (`AuthenticationError` 401, `BudgetExceededError` 402, `AirGapEgressError` 403, `NotFoundError` 404, `PolicyViolationError` 422 with structured `Findings`, `RateLimitError` 429, `UpstreamProviderError` 5xx).
2. **Marketplace Commercial Settlement Ledger (`core/platform/settlement.py` + `core/api/platform_routes.py`)**:
   - Zero-drift integer-cent splits (`85/15` verified third-party, `80/20` enterprise partner, `0/100` first-party), SPDX license attribution, cryptographic SHA-256 purchase & entitlement receipts, automatic `MarketplaceRegistry` installation, and `SQLitePlatformStore` WAL durability (`POST /v1/platform/marketplace/purchase`, `GET /v1/platform/marketplace/settlements`).
3. **Cross-SDK Cluster & Settlement Parity (`core/sdk/cluster_client.py`, `sdk/typescript/src/cluster.ts`)**:
   - Full `client.cluster` and Marketplace settlement parity across Python (`KeelwayClient` / `AsyncKeelwayClient`), TypeScript (`@keelway/sdk`), Go (`keelway-go`), Dev App (`platformApi.ts`), and Website Quickstart/Docs (`QuickstartTerminal.tsx`, `DocsHub.tsx`).

## Verification Evidence
- `sdk/go/client_test.go` (`go vet ./...` + `go test ./... -race` — `5/5` passed)
- `tests/test_marketplace_settlement_and_cluster_sdk.py` (`16/16` passed)
- `sdk/typescript/test/sdk.test.mjs` (`9/9` passed, zero runtime dependencies)
