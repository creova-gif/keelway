package keelway

import (
	"context"
	"net/http"
)

type KStackExecuteRequest struct {
	Name   string         `json:"name"`
	Inputs map[string]any `json:"inputs,omitempty"`
}

type SkillExecutionProof struct {
	ExecutionID       string         `json:"execution_id"`
	SkillName         string         `json:"skill_name"`
	SkillDigestSHA256 string         `json:"skill_digest_sha256"`
	Actor             string         `json:"actor"`
	Inputs            map[string]any `json:"inputs"`
	Outputs           map[string]any `json:"outputs"`
	PermissionsUsed   []string       `json:"permissions_used"`
	Success           bool           `json:"success"`
	DurationMS        float64        `json:"duration_ms"`
	TimestampUTC      string         `json:"timestamp_utc"`
	SignatureSHA256   string         `json:"signature_sha256"`
}

type KStackService struct{ client *Client }

func (s *KStackService) Execute(ctx context.Context, req KStackExecuteRequest) (*SkillExecutionProof, error) {
	if req.Inputs == nil {
		req.Inputs = map[string]any{}
	}
	var out struct {
		Proof SkillExecutionProof `json:"proof"`
	}
	if err := s.client.doJSON(ctx, http.MethodPost, "/v1/kstack/execute", nil, req, &out); err != nil {
		return nil, err
	}
	return &out.Proof, nil
}
