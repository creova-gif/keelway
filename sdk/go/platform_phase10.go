package keelway

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"strings"
)

type KBrainFactRecordRequest struct {
	WorkspaceID   string   `json:"workspace_id,omitempty"`
	Key           string   `json:"key"`
	Statement     string   `json:"statement"`
	Scope         string   `json:"scope,omitempty"`
	ProvenanceURI string   `json:"provenance_uri,omitempty"`
	Tags          []string `json:"tags,omitempty"`
	AutoApprove   bool     `json:"auto_approve"`
}

type KBrainFactRecord struct {
	ID                 string   `json:"id"`
	WorkspaceID        string   `json:"workspace_id"`
	Key                string   `json:"key"`
	Statement          string   `json:"statement"`
	Scope              string   `json:"scope"`
	Status             string   `json:"status"`
	ConflictWithFactID string   `json:"conflict_with_fact_id,omitempty"`
	ProvenanceURI      string   `json:"provenance_uri,omitempty"`
	Tags               []string `json:"tags"`
	CreatedBy          string   `json:"created_by,omitempty"`
	FactSHA256         string   `json:"fact_sha256"`
	CreatedAt          string   `json:"created_at,omitempty"`
}

type KBrainSearchParams struct {
	WorkspaceID      string
	Query            string
	MaxScope         string
	IncludeConflicts bool
	Limit            int
}

type KBrainSearchResultItem struct {
	KBrainFactRecord
	Score      float64 `json:"score,omitempty"`
	BM25Score  float64 `json:"bm25_score,omitempty"`
	NGramScore float64 `json:"ngram_score,omitempty"`
}

type KBrainSearchResponse struct {
	WorkspaceID  string                   `json:"workspace_id"`
	Query        string                   `json:"query"`
	MaxScope     string                   `json:"max_scope"`
	TotalMatches int                      `json:"total_matches"`
	Results      []KBrainSearchResultItem `json:"results"`
}

type KBrainFactResolveRequest struct {
	WorkspaceID string `json:"workspace_id,omitempty"`
	Resolution  string `json:"resolution"`
}

type KHubSkillDescriptor struct {
	SkillID            string `json:"skill_id,omitempty"`
	ID                 string `json:"id,omitempty"`
	Name               string `json:"name,omitempty"`
	Description        string `json:"description,omitempty"`
	Version            string `json:"version,omitempty"`
	Source             string `json:"source,omitempty"`
	SourceType         string `json:"source_type,omitempty"`
	BundleDigestSHA256 string `json:"bundle_digest_sha256,omitempty"`
	DigestSHA256       string `json:"digest_sha256,omitempty"`
	FilesCount         int    `json:"files_count,omitempty"`
	AirGapCompliant    bool   `json:"air_gap_compliant,omitempty"`
	AirGapReady        bool   `json:"air_gap_ready,omitempty"`
}

type KHubSkillListResponse struct {
	WorkspaceID         string                `json:"workspace_id"`
	TotalSkills         int                   `json:"total_skills"`
	AirGapCompliant     bool                  `json:"air_gap_compliant"`
	CatalogDigestSHA256 string                `json:"catalog_digest_sha256"`
	Skills              []KHubSkillDescriptor `json:"skills"`
}

type KHubMirrorVerifyRequest struct {
	WorkspaceID string   `json:"workspace_id,omitempty"`
	SkillIDs    []string `json:"skill_ids,omitempty"`
}

type KHubMirrorVerifyResponse struct {
	WorkspaceID         string `json:"workspace_id"`
	Verified            bool   `json:"verified"`
	MirrorFormat        string `json:"mirror_format"`
	SkillsVerified      int    `json:"skills_verified"`
	CatalogDigestSHA256 string `json:"catalog_digest_sha256"`
	VerifiedAt          string `json:"verified_at"`
}

func (p *PlatformService) RecordKBrainFact(ctx context.Context, req KBrainFactRecordRequest) (*KBrainFactRecord, error) {
	cleanKey := strings.TrimSpace(req.Key)
	if cleanKey == "" {
		return nil, fmt.Errorf("keelway: key must be non-empty")
	}
	cleanStatement := strings.TrimSpace(req.Statement)
	if cleanStatement == "" {
		return nil, fmt.Errorf("keelway: statement must be non-empty")
	}
	tags := req.Tags
	if tags == nil {
		tags = []string{}
	}
	body := map[string]any{
		"workspace_id":   firstString(req.WorkspaceID, "default"),
		"key":            cleanKey,
		"statement":      cleanStatement,
		"scope":          firstString(req.Scope, "project"),
		"provenance_uri": firstString(req.ProvenanceURI, "workspace"),
		"tags":           tags,
		"auto_approve":   req.AutoApprove,
	}
	return doPlatformJSON[KBrainFactRecord](ctx, p.client, http.MethodPost, "/v1/platform/kbrain/facts", nil, body)
}

func (p *PlatformService) SearchKBrainFacts(ctx context.Context, params KBrainSearchParams) (*KBrainSearchResponse, error) {
	q := wsQuery(params.WorkspaceID)
	q.Set("query", params.Query)
	q.Set("max_scope", firstString(params.MaxScope, "org"))
	q.Set("include_conflicts", strconv.FormatBool(params.IncludeConflicts))
	limit := params.Limit
	if limit <= 0 {
		limit = 10
	}
	q.Set("limit", strconv.Itoa(limit))
	return doPlatformJSON[KBrainSearchResponse](ctx, p.client, http.MethodGet, "/v1/platform/kbrain/search", q, nil)
}

func (p *PlatformService) ResolveKBrainFact(ctx context.Context, factID string, req KBrainFactResolveRequest) (*KBrainFactRecord, error) {
	resolution := strings.TrimSpace(firstString(req.Resolution, "approve"))
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"resolution":   resolution,
	}
	return doSegJSON[KBrainFactRecord](ctx, p.client, http.MethodPost, "/v1/platform/kbrain/facts/", factID, "factID", "/resolve", nil, body)
}

func (p *PlatformService) ListKHubSkills(ctx context.Context, workspaceID string) (*KHubSkillListResponse, error) {
	return doPlatformJSON[KHubSkillListResponse](ctx, p.client, http.MethodGet, "/v1/platform/khub/skills", wsQuery(workspaceID), nil)
}

func (p *PlatformService) VerifyKHubMirror(ctx context.Context, req KHubMirrorVerifyRequest) (*KHubMirrorVerifyResponse, error) {
	skillIDs := req.SkillIDs
	if skillIDs == nil {
		skillIDs = []string{}
	}
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"skill_ids":    skillIDs,
	}
	return doPlatformJSON[KHubMirrorVerifyResponse](ctx, p.client, http.MethodPost, "/v1/platform/khub/mirror/verify", nil, body)
}
