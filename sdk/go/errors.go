package keelway

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
)

// APIError is the base structured HTTP error returned by the Keelway API.
type APIError struct {
	StatusCode int
	Code       string
	Message    string
	Details    map[string]any
	Findings   []map[string]any
}

// Error formats the structured API error for diagnostic logging.
func (e *APIError) Error() string {
	if e == nil {
		return "<nil>"
	}
	if e.Code != "" {
		return fmt.Sprintf("keelway api error (%d %s): %s", e.StatusCode, e.Code, e.Message)
	}
	return fmt.Sprintf("keelway api error (%d): %s", e.StatusCode, e.Message)
}

// AuthenticationError represents HTTP 401 unauthorized or invalid bearer credentials.
type AuthenticationError struct{ APIError }

func (e *AuthenticationError) Unwrap() error { return &e.APIError }

// BudgetExceededError represents HTTP 402 tenant or request spend cap enforcement.
type BudgetExceededError struct{ APIError }

func (e *BudgetExceededError) Unwrap() error { return &e.APIError }

// AirGapEgressError represents HTTP 403 zero-egress air-gap or sovereign boundary rejection.
type AirGapEgressError struct{ APIError }

func (e *AirGapEgressError) Unwrap() error { return &e.APIError }

// NotFoundError represents HTTP 404 missing model, response, package, or tenant resource.
type NotFoundError struct{ APIError }

func (e *NotFoundError) Unwrap() error { return &e.APIError }

// PolicyViolationError represents HTTP 422 governance or Marketplace security scan rejection.
type PolicyViolationError struct {
	APIError
	RiskGrade string
}

func (e *PolicyViolationError) Unwrap() error { return &e.APIError }

// RateLimitError represents HTTP 429 RPM/TPM rate limit enforcement.
type RateLimitError struct{ APIError }

func (e *RateLimitError) Unwrap() error { return &e.APIError }

// UpstreamProviderError represents HTTP 502, 503, or 504 upstream inference gateway failures.
type UpstreamProviderError struct{ APIError }

func (e *UpstreamProviderError) Unwrap() error { return &e.APIError }

func defaultErrorCode(statusCode int) string {
	switch statusCode {
	case http.StatusUnauthorized:
		return "AUTHENTICATION_FAILED"
	case http.StatusPaymentRequired:
		return "BUDGET_EXCEEDED"
	case http.StatusForbidden:
		return "AIRGAP_EGRESS_BLOCKED"
	case http.StatusNotFound:
		return "NOT_FOUND"
	case http.StatusUnprocessableEntity:
		return "POLICY_VIOLATION"
	case http.StatusTooManyRequests:
		return "RATE_LIMIT_EXCEEDED"
	case http.StatusBadGateway, http.StatusServiceUnavailable, http.StatusGatewayTimeout:
		return "UPSTREAM_PROVIDER_ERROR"
	default:
		return "API_ERROR"
	}
}

func extractFindings(raw any) []map[string]any {
	items, ok := raw.([]any)
	if !ok || len(items) == 0 {
		return nil
	}
	out := make([]map[string]any, 0, len(items))
	for _, item := range items {
		if m, ok := item.(map[string]any); ok {
			out = append(out, m)
		}
	}
	return out
}

func firstString(values ...any) string {
	for _, v := range values {
		if s, ok := v.(string); ok && strings.TrimSpace(s) != "" {
			return strings.TrimSpace(s)
		}
	}
	return ""
}

func parseAPIError(statusCode int, body []byte) error {
	details := make(map[string]any)
	var findings []map[string]any
	var code, msg, riskGrade string

	trimmed := strings.TrimSpace(string(body))
	var payload map[string]any
	if trimmed != "" && json.Unmarshal(body, &payload) == nil && payload != nil {
		for k, v := range payload {
			if k != "detail" {
				details[k] = v
			}
		}
		switch d := payload["detail"].(type) {
		case string:
			msg = strings.TrimSpace(d)
		case map[string]any:
			for k, v := range d {
				details[k] = v
			}
			msg = firstString(d["message"], d["reason"], d["error"])
			code = firstString(d["code"])
			riskGrade = firstString(d["risk_grade"], d["riskGrade"])
			findings = extractFindings(d["findings"])
		case []any:
			details["validation_errors"] = d
			if rawDetail, err := json.Marshal(d); err == nil {
				msg = string(rawDetail)
			}
		}
		if errObj, ok := payload["error"].(map[string]any); ok {
			msg = firstString(msg, errObj["message"], errObj["reason"])
			code = firstString(code, errObj["code"], errObj["type"])
		}
		msg = firstString(msg, payload["message"], payload["reason"], payload["error"])
		code = firstString(code, payload["code"])
		riskGrade = firstString(riskGrade, payload["risk_grade"], payload["riskGrade"])
		if len(findings) == 0 {
			findings = extractFindings(payload["findings"])
		}
	}

	if riskGrade != "" {
		details["risk_grade"] = riskGrade
	}
	if len(findings) > 0 {
		details["findings"] = findings
	}
	if code == "" {
		code = defaultErrorCode(statusCode)
	}
	if msg == "" {
		msg = firstString(trimmed, http.StatusText(statusCode), fmt.Sprintf("HTTP %d", statusCode))
	}

	base := APIError{
		StatusCode: statusCode,
		Code:       code,
		Message:    msg,
		Details:    details,
		Findings:   findings,
	}
	switch statusCode {
	case http.StatusUnauthorized:
		return &AuthenticationError{APIError: base}
	case http.StatusPaymentRequired:
		return &BudgetExceededError{APIError: base}
	case http.StatusForbidden:
		return &AirGapEgressError{APIError: base}
	case http.StatusNotFound:
		return &NotFoundError{APIError: base}
	case http.StatusUnprocessableEntity:
		return &PolicyViolationError{APIError: base, RiskGrade: riskGrade}
	case http.StatusTooManyRequests:
		return &RateLimitError{APIError: base}
	case http.StatusBadGateway, http.StatusServiceUnavailable, http.StatusGatewayTimeout:
		return &UpstreamProviderError{APIError: base}
	default:
		return &base
	}
}
