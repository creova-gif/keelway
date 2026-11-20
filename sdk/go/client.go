package keelway

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const (
	DefaultBaseURL = "http://127.0.0.1:7420"
	DefaultTimeout = 30 * time.Second
	sdkUserAgent   = "keelway-go/1.0.0"
)

type Option func(*Client)

func WithAPIKey(apiKey string) Option {
	return func(c *Client) { c.apiKey = strings.TrimSpace(apiKey) }
}
func WithTimeout(d time.Duration) Option {
	return func(c *Client) { c.timeout, c.timeoutSet = d, true }
}
func WithHTTPClient(hc *http.Client) Option {
	return func(c *Client) {
		if hc != nil {
			c.httpClient = hc
		}
	}
}
func WithHeader(k, v string) Option {
	return func(c *Client) {
		if strings.TrimSpace(k) != "" {
			c.headers[k] = v
		}
	}
}

type Client struct {
	BaseURL    string
	Responses  *ResponsesService
	Routing    *RoutingService
	Platform   *PlatformService
	Cluster    *ClusterService
	KStack     *KStackService
	Agents     *AgentsService
	apiKey     string
	httpClient *http.Client
	timeout    time.Duration
	timeoutSet bool
	headers    map[string]string
}

func NewClient(baseURL string, opts ...Option) *Client {
	cleanBase := firstString(strings.TrimRight(strings.TrimSpace(baseURL), "/"), DefaultBaseURL)
	c := &Client{BaseURL: cleanBase, timeout: DefaultTimeout, headers: make(map[string]string)}
	for _, opt := range opts {
		if opt != nil {
			opt(c)
		}
	}
	if c.httpClient == nil {
		c.httpClient = &http.Client{Timeout: c.timeout}
	} else if c.timeoutSet {
		cloned := *c.httpClient
		cloned.Timeout = c.timeout
		c.httpClient = &cloned
	}
	c.Responses, c.Routing = &ResponsesService{client: c}, &RoutingService{client: c}
	c.Platform, c.Cluster = &PlatformService{client: c}, &ClusterService{client: c}
	c.KStack, c.Agents = &KStackService{client: c}, &AgentsService{client: c}
	return c
}

func (c *Client) newRequest(ctx context.Context, method, path string, query url.Values, reqBody any, sse bool) (*http.Request, error) {
	if ctx == nil {
		ctx = context.Background()
	}
	target := c.BaseURL + "/" + strings.TrimLeft(path, "/")
	if len(query) > 0 {
		target += "?" + query.Encode()
	}
	var bodyReader io.Reader
	if reqBody != nil {
		encoded, err := json.Marshal(reqBody)
		if err != nil {
			return nil, fmt.Errorf("keelway: marshal request: %w", err)
		}
		bodyReader = bytes.NewReader(encoded)
	}
	req, err := http.NewRequestWithContext(ctx, method, target, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("keelway: create request: %w", err)
	}
	req.Header.Set("User-Agent", sdkUserAgent)
	req.Header.Set("Accept", map[bool]string{false: "application/json", true: "text/event-stream"}[sse])
	if reqBody != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	for k, v := range c.headers {
		req.Header.Set(k, v)
	}
	if c.apiKey != "" && req.Header.Get("Authorization") == "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
	return req, nil
}

func (c *Client) doJSON(ctx context.Context, method, path string, query url.Values, reqBody any, out any) error {
	req, err := c.newRequest(ctx, method, path, query, reqBody, false)
	if err != nil {
		return err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return parseAPIError(resp.StatusCode, raw)
	}
	if out == nil || len(bytes.TrimSpace(raw)) == 0 {
		return nil
	}
	return json.Unmarshal(raw, out)
}

type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type TokenUsage struct {
	InputTokens  int `json:"input_tokens,omitempty"`
	OutputTokens int `json:"output_tokens,omitempty"`
	PromptTokens int `json:"prompt_tokens,omitempty"`
	TotalTokens  int `json:"total_tokens"`
}

type ResponseCreateRequest struct {
	Model                string         `json:"model,omitempty"`
	Input                any            `json:"input"`
	Instructions         string         `json:"instructions,omitempty"`
	PreviousResponseID   string         `json:"previous_response_id,omitempty"`
	Temperature          *float64       `json:"temperature,omitempty"`
	MaxOutputTokens      int            `json:"max_output_tokens,omitempty"`
	Text                 map[string]any `json:"text,omitempty"`
	Store                *bool          `json:"store,omitempty"`
	PrivacyLevel         string         `json:"privacy_level,omitempty"`
	RequiredCapabilities []string       `json:"required_capabilities,omitempty"`
	MaxCostUSD           float64        `json:"max_cost_usd,omitempty"`
	Speculative          bool           `json:"speculative,omitempty"`
	DraftModel           string         `json:"draft_model,omitempty"`
	Stream               bool           `json:"stream"`
}

type ResponseResult struct {
	ID                 string           `json:"id"`
	Object             string           `json:"object,omitempty"`
	CreatedAt          int64            `json:"created_at,omitempty"`
	Status             string           `json:"status,omitempty"`
	Model              string           `json:"model"`
	PreviousResponseID string           `json:"previous_response_id,omitempty"`
	Output             []map[string]any `json:"output,omitempty"`
	OutputText         string           `json:"output_text"`
	Usage              *TokenUsage      `json:"usage,omitempty"`
	KeelwayMetadata    map[string]any   `json:"keelway_metadata,omitempty"`
}

type StreamEvent struct {
	Type         string          `json:"type,omitempty"`
	Event        string          `json:"event,omitempty"`
	ResponseID   string          `json:"response_id,omitempty"`
	ItemID       string          `json:"item_id,omitempty"`
	OutputIndex  int             `json:"output_index,omitempty"`
	ContentIndex int             `json:"content_index,omitempty"`
	Delta        string          `json:"delta,omitempty"`
	Data         string          `json:"-"`
	Response     *ResponseResult `json:"response,omitempty"`
	Error        map[string]any  `json:"error,omitempty"`
}

type SSEStream struct {
	ctx    context.Context
	body   io.ReadCloser
	reader *bufio.Reader
	closed bool
}

func buildStreamEvent(eventName string, dataLines []string) (*StreamEvent, bool, bool) {
	joined := strings.TrimSpace(strings.Join(dataLines, "\n"))
	if len(dataLines) == 0 || joined == "" {
		return nil, false, false
	}
	if joined == "[DONE]" {
		return nil, false, true
	}
	ev := &StreamEvent{Data: joined, Event: eventName}
	_ = json.Unmarshal([]byte(joined), ev)
	ev.Event, ev.Type = firstString(ev.Event, eventName), firstString(ev.Type, eventName)
	return ev, true, false
}

func (s *SSEStream) Next() (*StreamEvent, error) {
	if s.closed {
		return nil, io.EOF
	}
	if err := s.ctx.Err(); err != nil {
		_ = s.Close()
		return nil, err
	}
	var eventName string
	var dataLines []string
	for {
		rawLine, readErr := s.reader.ReadString('\n')
		if rawLine != "" || readErr == nil {
			line := strings.TrimRight(rawLine, "\r\n")
			if line == "" {
				ev, ok, done := buildStreamEvent(eventName, dataLines)
				eventName, dataLines = "", nil
				if done {
					_ = s.Close()
					return nil, io.EOF
				}
				if ok {
					return ev, nil
				}
			} else if strings.HasPrefix(line, "event:") {
				eventName = strings.TrimSpace(strings.TrimPrefix(line, "event:"))
			} else if strings.HasPrefix(line, "data:") {
				val := strings.TrimPrefix(strings.TrimPrefix(line, "data:"), " ")
				if strings.TrimSpace(val) == "[DONE]" && len(dataLines) == 0 {
					_ = s.Close()
					return nil, io.EOF
				}
				dataLines = append(dataLines, val)
			}
		}
		if readErr != nil {
			_ = s.Close()
			if errors.Is(readErr, io.EOF) {
				if ev, ok, done := buildStreamEvent(eventName, dataLines); ok && !done {
					return ev, nil
				}
				return nil, io.EOF
			}
			return nil, readErr
		}
	}
}

func (s *SSEStream) Close() error {
	if s.closed || s.body == nil {
		s.closed = true
		return nil
	}
	s.closed = true
	return s.body.Close()
}

type ResponsesService struct{ client *Client }

func (r *ResponsesService) Create(ctx context.Context, req ResponseCreateRequest) (*ResponseResult, error) {
	req.Stream, req.PrivacyLevel = false, firstString(req.PrivacyLevel, "standard")
	var out ResponseResult
	if err := r.client.doJSON(ctx, http.MethodPost, "/v1/responses", nil, req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (r *ResponsesService) Stream(ctx context.Context, req ResponseCreateRequest) (*SSEStream, error) {
	req.Stream, req.PrivacyLevel = true, firstString(req.PrivacyLevel, "standard")
	httpReq, err := r.client.newRequest(ctx, http.MethodPost, "/v1/responses", nil, req, true)
	if err != nil {
		return nil, err
	}
	resp, err := r.client.httpClient.Do(httpReq)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		defer resp.Body.Close()
		raw, _ := io.ReadAll(resp.Body)
		return nil, parseAPIError(resp.StatusCode, raw)
	}
	return &SSEStream{ctx: httpReq.Context(), body: resp.Body, reader: bufio.NewReader(resp.Body)}, nil
}

type RoutingExplainRequest struct {
	Model                string        `json:"model,omitempty"`
	Prompt               string        `json:"prompt,omitempty"`
	Messages             []ChatMessage `json:"messages,omitempty"`
	MaxTokens            int           `json:"max_tokens,omitempty"`
	PrivacyLevel         string        `json:"privacy_level,omitempty"`
	RequiredCapabilities []string      `json:"required_capabilities,omitempty"`
	MaxCostUSD           float64       `json:"max_cost_usd,omitempty"`
	PreferredProvider    string        `json:"preferred_provider,omitempty"`
	CategoryPreference   string        `json:"category_preference,omitempty"`
}

type RoutingExplanation struct {
	DecisionID           string         `json:"decision_id,omitempty"`
	RequestedModel       string         `json:"requested_model,omitempty"`
	SelectedModel        string         `json:"selected_model"`
	SelectedProvider     string         `json:"selected_provider,omitempty"`
	FallbackChain        []string       `json:"fallback_chain,omitempty"`
	Reason               string         `json:"reason,omitempty"`
	RoutingReason        string         `json:"routing_reason,omitempty"`
	GovernanceProvenance map[string]any `json:"governance_provenance,omitempty"`
	Provenance           map[string]any `json:"provenance,omitempty"`
	EstimatedCostUSD     float64        `json:"estimated_cost_usd,omitempty"`
	PrivacyLevel         string         `json:"privacy_level,omitempty"`
	PrivacyCompliant     bool           `json:"privacy_compliant,omitempty"`
}

type RoutingService struct{ client *Client }

func (r *RoutingService) Explain(ctx context.Context, req RoutingExplainRequest) (*RoutingExplanation, error) {
	req.PrivacyLevel = firstString(req.PrivacyLevel, "standard")
	var out RoutingExplanation
	if err := r.client.doJSON(ctx, http.MethodPost, "/v1/routing/explain", nil, req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
