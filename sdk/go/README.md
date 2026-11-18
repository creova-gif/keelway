# `keelway-go`

Official zero-dependency Go SDK (`github.com/keelway/keelway-go`) for the **Keelway Sovereign & Hybrid AI Platform**.

- **Zero External Dependencies**: Built exclusively on the Go 1.22+ standard library (`net/http`, `encoding/json`, `bufio`, `context`).
- **Chunk-Safe SSE Streaming**: `Responses.Stream` buffers arbitrary TCP chunk splits via `bufio.Reader` and terminates cleanly with `io.EOF` on `data: [DONE]`.
- **Fail-Closed Governance Errors**: Deterministic `errors.As` support across air-gap egress blocks, spend caps, rate limits, and Marketplace security scan findings.

## Installation

```bash
go get github.com/keelway/keelway-go
```

## Quickstart

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"time"

	keelway "github.com/keelway/keelway-go"
)

func main() {
	ctx := context.Background()
	client := keelway.NewClient(
		"http://127.0.0.1:7420",
		keelway.WithAPIKey(os.Getenv("KEELWAY_API_KEY")),
		keelway.WithTimeout(30*time.Second),
	)

	// 1. Inspect 4D routing provenance prior to inference
	route, err := client.Routing.Explain(ctx, keelway.RoutingExplainRequest{
		Prompt:       "Summarize quarterly treasury risk ledger",
		PrivacyLevel: "private",
	})
	if err != nil {
		panic(err)
	}
	fmt.Println("Selected model:", route.SelectedModel)

	// 2. Stream stateful responses across SSE frames
	stream, err := client.Responses.Stream(ctx, keelway.ResponseCreateRequest{
		Model:        "keelway-core:7b",
		Input:        "Draft an air-gapped deployment checklist.",
		PrivacyLevel: "private",
	})
	if err != nil {
		var airGapErr *keelway.AirGapEgressError
		if errors.As(err, &airGapErr) {
			fmt.Println("Blocked by air-gap policy:", airGapErr.Message)
			return
		}
		panic(err)
	}
	defer stream.Close()

	for {
		ev, err := stream.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			panic(err)
		}
		fmt.Print(ev.Delta)
	}
}
```

## Surface Overview

| Service | Methods | Endpoints |
|---------|---------|-----------|
| `client.Responses` | `Create`, `Stream` | `POST /v1/responses` |
| `client.Routing` | `Explain` | `POST /v1/routing/explain` |
| `client.Platform` | `GetOverview`, `ListAgents`, `DispatchTeam`, `ListIssues`, `CreateIssue`, `ListMarketplacePackages`, `ScanMarketplacePackage`, `PublishMarketplacePackage`, `InstallMarketplacePackage`, `CompileBlueprint`, `GetEnterprisePolicy`, `EvaluateCompliance` | `/v1/platform/*` |
| `client.Cluster` | `ListNodes`, `Schedule`, `ListLifecycle` | `/v1/cluster/*` |

## Typed Error Hierarchy (`errors.As`)

| HTTP Status | Go Error Type | Default Code |
|-------------|---------------|--------------|
| `401` | `*keelway.AuthenticationError` | `AUTHENTICATION_FAILED` |
| `402` | `*keelway.BudgetExceededError` | `BUDGET_EXCEEDED` |
| `403` | `*keelway.AirGapEgressError` | `AIRGAP_EGRESS_BLOCKED` |
| `404` | `*keelway.NotFoundError` | `NOT_FOUND` |
| `422` | `*keelway.PolicyViolationError` (`Findings`, `RiskGrade`) | `POLICY_VIOLATION` |
| `429` | `*keelway.RateLimitError` | `RATE_LIMIT_EXCEEDED` |
| `502`/`503`/`504` | `*keelway.UpstreamProviderError` | `UPSTREAM_PROVIDER_ERROR` |
