package keelway

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
)

type AgentRegistryRecord struct {
	ID          int64  `json:"id"`
	Name        string `json:"name"`
	Version     string `json:"version"`
	Owner       string `json:"owner"`
	Description string `json:"description,omitempty"`
	Digest      string `json:"digest"`
	Enabled     bool   `json:"enabled"`
	CreatedAt   string `json:"created_at,omitempty"`
	UpdatedAt   string `json:"updated_at,omitempty"`
}

type AgentRegistryListResponse struct {
	Manifests []AgentRegistryRecord `json:"manifests"`
}

type AgentRegistryToggleResponse struct {
	ID        int64  `json:"id"`
	Enabled   bool   `json:"enabled"`
	UpdatedAt string `json:"updated_at,omitempty"`
}

type AgentsService struct{ client *Client }

func (s *AgentsService) ListRegistry(ctx context.Context, enabledOnly bool) (*AgentRegistryListResponse, error) {
	var out AgentRegistryListResponse
	query := url.Values{}
	if enabledOnly {
		query.Set("enabled_only", "true")
	}
	if err := s.client.doJSON(ctx, http.MethodGet, "/v1/agents/registry", query, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (s *AgentsService) ToggleManifest(ctx context.Context, name, version string, enabled bool) (*AgentRegistryToggleResponse, error) {
	path := fmt.Sprintf("/v1/agents/registry/%s/%s/toggle", url.PathEscape(name), url.PathEscape(version))
	var out AgentRegistryToggleResponse
	if err := s.client.doJSON(ctx, http.MethodPost, path, nil, map[string]any{"enabled": enabled}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
