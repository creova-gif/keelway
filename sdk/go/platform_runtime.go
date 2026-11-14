package keelway

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

type SecretPutRequest struct {
	Name        string `json:"name"`
	SecretValue string `json:"secret_value"`
	WorkspaceID string `json:"workspace_id,omitempty"`
	Namespace   string `json:"namespace,omitempty"`
	Description string `json:"description,omitempty"`
}
type SecretRotateRequest struct {
	SecretValue string `json:"secret_value"`
	WorkspaceID string `json:"workspace_id,omitempty"`
	Namespace   string `json:"namespace,omitempty"`
}
type VaultSecretMetadata struct {
	Name              string `json:"name"`
	WorkspaceID       string `json:"workspace_id,omitempty"`
	Namespace         string `json:"namespace"`
	MaskedPreview     string `json:"masked_preview"`
	FingerprintSHA256 string `json:"fingerprint_sha256"`
	Version           int    `json:"version"`
	UpdatedAt         string `json:"updated_at,omitempty"`
}
type VaultSecretList struct {
	WorkspaceID string                `json:"workspace_id,omitempty"`
	Secrets     []VaultSecretMetadata `json:"secrets"`
	Total       int                   `json:"total,omitempty"`
}
type PlatformDeleteResult struct {
	Deleted     bool   `json:"deleted"`
	Revoked     bool   `json:"revoked,omitempty"`
	Name        string `json:"name,omitempty"`
	WebhookID   string `json:"webhook_id,omitempty"`
	WorkspaceID string `json:"workspace_id,omitempty"`
}
type SecretDeleteResult = PlatformDeleteResult
type WebhookDeleteResult = PlatformDeleteResult

type WebhookCreateRequest struct {
	URL         string   `json:"url"`
	Events      []string `json:"events,omitempty"`
	Description string   `json:"description,omitempty"`
	Secret      string   `json:"secret,omitempty"`
	WorkspaceID string   `json:"workspace_id,omitempty"`
}
type WebhookRecord struct {
	ID          string   `json:"id"`
	WorkspaceID string   `json:"workspace_id,omitempty"`
	URL         string   `json:"url"`
	Events      []string `json:"events"`
	Description string   `json:"description,omitempty"`
	Active      bool     `json:"active,omitempty"`
}
type WebhookList struct {
	WorkspaceID string           `json:"workspace_id,omitempty"`
	Webhooks    []WebhookRecord  `json:"webhooks"`
	Deliveries  []map[string]any `json:"deliveries,omitempty"`
	Total       int              `json:"total,omitempty"`
}
type WebhookTestReceipt struct {
	WebhookID string            `json:"webhook_id"`
	EventID   string            `json:"event_id,omitempty"`
	Signature string            `json:"signature"`
	Headers   map[string]string `json:"headers,omitempty"`
	Delivered bool              `json:"delivered"`
}
type WebhookVerifyRequest struct {
	Payload          any    `json:"payload"`
	Signature        string `json:"signature"`
	Secret           string `json:"secret"`
	Timestamp        any    `json:"timestamp,omitempty"`
	ToleranceSeconds int    `json:"tolerance_seconds,omitempty"`
}
type WebhookVerifyResult struct {
	Valid  bool   `json:"valid"`
	Reason string `json:"reason,omitempty"`
}
type ExecutionRunStartRequest struct {
	Kind        string         `json:"kind,omitempty"`
	TargetID    string         `json:"target_id"`
	Objective   string         `json:"objective"`
	WorkspaceID string         `json:"workspace_id,omitempty"`
	RequiresP10 bool           `json:"requires_p10,omitempty"`
	ActorRole   string         `json:"actor_role,omitempty"`
	Metadata    map[string]any `json:"metadata,omitempty"`
}
type ExecutionEvent struct {
	Type      string         `json:"type,omitempty"`
	Event     string         `json:"event,omitempty"`
	RunID     string         `json:"run_id,omitempty"`
	Seq       int            `json:"seq,omitempty"`
	Stage     string         `json:"stage,omitempty"`
	Status    string         `json:"status,omitempty"`
	Message   string         `json:"message,omitempty"`
	Timestamp string         `json:"timestamp,omitempty"`
	Payload   map[string]any `json:"-"`
	Raw       string         `json:"-"`
}
type ExecutionRunSnapshot struct {
	RunID       string           `json:"run_id"`
	WorkspaceID string           `json:"workspace_id,omitempty"`
	Kind        string           `json:"kind"`
	TargetID    string           `json:"target_id"`
	Objective   string           `json:"objective"`
	Status      string           `json:"status"`
	RequiresP10 bool             `json:"requires_p10,omitempty"`
	Events      []ExecutionEvent `json:"events,omitempty"`
}
type ExecutionP10Request struct {
	Decision    string `json:"decision"`
	Approver    string `json:"approver,omitempty"`
	ActorID     string `json:"actor_id,omitempty"`
	Role        string `json:"role,omitempty"`
	Reason      string `json:"reason,omitempty"`
	WorkspaceID string `json:"workspace_id,omitempty"`
}

type ExecutionEventStream struct {
	ctx     context.Context
	body    io.ReadCloser
	reader  *bufio.Reader
	current ExecutionEvent
	err     error
	closed  bool
}

func decodeExecutionFrame(eventName string, dataLines []string) (ExecutionEvent, bool, bool) {
	joined := strings.TrimSpace(strings.Join(dataLines, "\n"))
	if len(dataLines) == 0 || joined == "" {
		return ExecutionEvent{}, false, false
	}
	if joined == "[DONE]" {
		return ExecutionEvent{}, false, true
	}
	ev := ExecutionEvent{Raw: joined, Event: eventName}
	_ = json.Unmarshal([]byte(joined), &ev.Payload)
	_ = json.Unmarshal([]byte(joined), &ev)
	ev.Event, ev.Type = firstString(ev.Event, ev.Type, eventName), firstString(ev.Type, ev.Event, eventName)
	return ev, true, false
}

func (s *ExecutionEventStream) Next() bool {
	if s.closed {
		return false
	}
	if err := s.ctx.Err(); err != nil {
		s.err = err
		_ = s.Close()
		return false
	}
	var eventName string
	var dataLines []string
	for {
		rawLine, readErr := s.reader.ReadString('\n')
		if rawLine != "" || readErr == nil {
			line := strings.TrimRight(rawLine, "\r\n")
			switch {
			case line == "":
				ev, ok, done := decodeExecutionFrame(eventName, dataLines)
				eventName, dataLines = "", nil
				if done {
					_ = s.Close()
					return false
				}
				if ok {
					s.current = ev
					return true
				}
			case strings.HasPrefix(line, "event:"):
				eventName = strings.TrimSpace(strings.TrimPrefix(line, "event:"))
			case strings.HasPrefix(line, "data:"):
				val := strings.TrimPrefix(strings.TrimPrefix(line, "data:"), " ")
				if strings.TrimSpace(val) == "[DONE]" && len(dataLines) == 0 {
					_ = s.Close()
					return false
				}
				dataLines = append(dataLines, val)
			}
		}
		if readErr != nil {
			_ = s.Close()
			if errors.Is(readErr, io.EOF) {
				if ev, ok, done := decodeExecutionFrame(eventName, dataLines); ok && !done {
					s.current = ev
					return true
				}
				return false
			}
			s.err = readErr
			return false
		}
	}
}

func (s *ExecutionEventStream) Event() ExecutionEvent { return s.current }
func (s *ExecutionEventStream) Err() error            { return s.err }
func (s *ExecutionEventStream) Close() error {
	if s.closed || s.body == nil {
		s.closed = true
		return nil
	}
	s.closed = true
	return s.body.Close()
}

func wsQuery(workspaceID string) url.Values {
	return url.Values{"workspace_id": {firstString(workspaceID, "default")}}
}

func pathSeg(raw, name string) (string, error) {
	if clean := strings.TrimSpace(raw); clean != "" {
		return url.PathEscape(clean), nil
	}
	return "", fmt.Errorf("keelway: %s must be non-empty", name)
}

func doPlatformJSON[T any](ctx context.Context, c *Client, method, path string, query url.Values, body any) (*T, error) {
	var out T
	if err := c.doJSON(ctx, method, path, query, body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func doSegJSON[T any](ctx context.Context, c *Client, method, prefix, id, field, suffix string, q url.Values, body any) (*T, error) {
	seg, err := pathSeg(id, field)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[T](ctx, c, method, prefix+seg+suffix, q, body)
}

func (p *PlatformService) ListDocs(ctx context.Context, workspaceID string) (*DocList, error) {
	return doPlatformJSON[DocList](ctx, p.client, http.MethodGet, "/v1/platform/docs", wsQuery(workspaceID), nil)
}
func (p *PlatformService) CreateDoc(ctx context.Context, req DocUpsertRequest) (*WorkspaceDoc, error) {
	req.DiataxisKind, req.WorkspaceID = firstString(req.DiataxisKind, "reference"), firstString(req.WorkspaceID, "default")
	return doPlatformJSON[WorkspaceDoc](ctx, p.client, http.MethodPost, "/v1/platform/docs", nil, req)
}
func (p *PlatformService) UpdateDoc(ctx context.Context, docID string, req DocUpsertRequest) (*WorkspaceDoc, error) {
	req.DiataxisKind, req.WorkspaceID = firstString(req.DiataxisKind, "reference"), firstString(req.WorkspaceID, "default")
	return doSegJSON[WorkspaceDoc](ctx, p.client, http.MethodPut, "/v1/platform/docs/", docID, "docID", "", nil, req)
}
func (p *PlatformService) UpdateIssue(ctx context.Context, issueID string, req IssuePatchRequest) (*Issue, error) {
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	return doSegJSON[Issue](ctx, p.client, http.MethodPatch, "/v1/platform/pm/issues/", issueID, "issueID", "", wsQuery(req.WorkspaceID), req)
}
func (p *PlatformService) ListFeedback(ctx context.Context, workspaceID string) (*FeedbackList, error) {
	return doPlatformJSON[FeedbackList](ctx, p.client, http.MethodGet, "/v1/platform/product/feedback", wsQuery(workspaceID), nil)
}
func (p *PlatformService) CreateFeedback(ctx context.Context, req FeedbackCreateRequest) (*FeedbackEntry, error) {
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	if req.ImpactScore == 0 {
		req.ImpactScore = 8.5
	}
	return doPlatformJSON[FeedbackEntry](ctx, p.client, http.MethodPost, "/v1/platform/product/feedback", nil, req)
}
func (p *PlatformService) ScanWorkspaceSecurity(ctx context.Context, req WorkspaceSecurityScanRequest) (*WorkspaceSecurityScanReport, error) {
	t, c := firstString(req.TargetName, req.TargetPath, "workspace-snippet"), firstString(req.Content, req.Snippet)
	req.TargetName, req.TargetPath, req.Content, req.Snippet, req.WorkspaceID = t, t, c, c, firstString(req.WorkspaceID, "default")
	return doPlatformJSON[WorkspaceSecurityScanReport](ctx, p.client, http.MethodPost, "/v1/platform/security/scan", nil, req)
}
func (p *PlatformService) ListWorkspaces(ctx context.Context) (*WorkspaceList, error) {
	return doPlatformJSON[WorkspaceList](ctx, p.client, http.MethodGet, "/v1/platform/workspaces", nil, nil)
}
func (p *PlatformService) CreateWorkspace(ctx context.Context, req WorkspaceCreateRequest) (*WorkspaceRecord, error) {
	req.Branch, req.IsolationMode = firstString(req.Branch, "main"), firstString(req.IsolationMode, "seatbelt_local")
	return doPlatformJSON[WorkspaceRecord](ctx, p.client, http.MethodPost, "/v1/platform/workspaces", nil, req)
}
func (p *PlatformService) ListRBACMembers(ctx context.Context, workspaceID string) (*RBACMemberList, error) {
	return doPlatformJSON[RBACMemberList](ctx, p.client, http.MethodGet, "/v1/platform/rbac/members", wsQuery(workspaceID), nil)
}
func (p *PlatformService) UpsertRBACMember(ctx context.Context, req RBACMemberUpsertRequest) (*RBACMember, error) {
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	return doPlatformJSON[RBACMember](ctx, p.client, http.MethodPost, "/v1/platform/rbac/members", nil, req)
}
func (p *PlatformService) CheckRBAC(ctx context.Context, req RBACCheckRequest) (*RBACCheckResult, error) {
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	return doPlatformJSON[RBACCheckResult](ctx, p.client, http.MethodPost, "/v1/platform/rbac/check", nil, req)
}
func (p *PlatformService) ListSecrets(ctx context.Context, workspaceID string) (*VaultSecretList, error) {
	return doPlatformJSON[VaultSecretList](ctx, p.client, http.MethodGet, "/v1/platform/vault/secrets", wsQuery(workspaceID), nil)
}
func (p *PlatformService) PutSecret(ctx context.Context, req SecretPutRequest) (*VaultSecretMetadata, error) {
	req.WorkspaceID, req.Namespace = firstString(req.WorkspaceID, "default"), firstString(req.Namespace, "byom")
	return doPlatformJSON[VaultSecretMetadata](ctx, p.client, http.MethodPost, "/v1/platform/vault/secrets", nil, req)
}
func (p *PlatformService) RotateSecret(ctx context.Context, name string, req SecretRotateRequest) (*VaultSecretMetadata, error) {
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	return doSegJSON[VaultSecretMetadata](ctx, p.client, http.MethodPost, "/v1/platform/vault/secrets/", name, "name", "/rotate", nil, req)
}
func (p *PlatformService) DeleteSecret(ctx context.Context, workspaceID, name string) (*SecretDeleteResult, error) {
	return doSegJSON[SecretDeleteResult](ctx, p.client, http.MethodDelete, "/v1/platform/vault/secrets/", name, "name", "", wsQuery(workspaceID), nil)
}
func (p *PlatformService) ListWebhooks(ctx context.Context, workspaceID string) (*WebhookList, error) {
	return doPlatformJSON[WebhookList](ctx, p.client, http.MethodGet, "/v1/platform/webhooks", wsQuery(workspaceID), nil)
}
func (p *PlatformService) CreateWebhook(ctx context.Context, req WebhookCreateRequest) (*WebhookRecord, error) {
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	if len(req.Events) == 0 {
		req.Events = []string{"*"}
	}
	return doPlatformJSON[WebhookRecord](ctx, p.client, http.MethodPost, "/v1/platform/webhooks", nil, req)
}
func (p *PlatformService) DeleteWebhook(ctx context.Context, webhookID string) (*WebhookDeleteResult, error) {
	return doSegJSON[WebhookDeleteResult](ctx, p.client, http.MethodDelete, "/v1/platform/webhooks/", webhookID, "webhookID", "", wsQuery("default"), nil)
}
func (p *PlatformService) TestWebhook(ctx context.Context, webhookID string) (*WebhookTestReceipt, error) {
	body := map[string]any{"event_type": "agent.run.completed", "workspace_id": "default"}
	return doSegJSON[WebhookTestReceipt](ctx, p.client, http.MethodPost, "/v1/platform/webhooks/", webhookID, "webhookID", "/test", nil, body)
}
func (p *PlatformService) VerifyWebhook(ctx context.Context, req WebhookVerifyRequest) (*WebhookVerifyResult, error) {
	if req.ToleranceSeconds == 0 {
		req.ToleranceSeconds = 300
	}
	return doPlatformJSON[WebhookVerifyResult](ctx, p.client, http.MethodPost, "/v1/platform/webhooks/verify", nil, req)
}
func (p *PlatformService) StartExecutionRun(ctx context.Context, req ExecutionRunStartRequest) (*ExecutionRunSnapshot, error) {
	body := map[string]any{"kind": firstString(req.Kind, "agent"), "target_id": req.TargetID, "objective": req.Objective, "workspace_id": firstString(req.WorkspaceID, "default"), "requires_p10": req.RequiresP10, "stream": false}
	if req.ActorRole != "" {
		body["actor_role"] = req.ActorRole
	}
	if req.Metadata != nil {
		body["metadata"] = req.Metadata
	}
	return doPlatformJSON[ExecutionRunSnapshot](ctx, p.client, http.MethodPost, "/v1/platform/execution/runs", nil, body)
}
func (p *PlatformService) ResolveExecutionP10(ctx context.Context, runID string, req ExecutionP10Request) (*ExecutionRunSnapshot, error) {
	req.Approver = firstString(req.Approver, req.ActorID, "local-operator")
	return doSegJSON[ExecutionRunSnapshot](ctx, p.client, http.MethodPost, "/v1/platform/execution/runs/", runID, "runID", "/p10", nil, req)
}
func (p *PlatformService) StreamExecutionEvents(ctx context.Context, runID string) (*ExecutionEventStream, error) {
	seg, err := pathSeg(runID, "runID")
	if err != nil {
		return nil, err
	}
	httpReq, err := p.client.newRequest(ctx, http.MethodGet, "/v1/platform/execution/runs/"+seg+"/events", nil, nil, true)
	if err != nil {
		return nil, err
	}
	resp, err := p.client.httpClient.Do(httpReq)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		defer resp.Body.Close()
		raw, _ := io.ReadAll(resp.Body)
		return nil, parseAPIError(resp.StatusCode, raw)
	}
	return &ExecutionEventStream{ctx: httpReq.Context(), body: resp.Body, reader: bufio.NewReader(resp.Body)}, nil
}
