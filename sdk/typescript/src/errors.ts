/**
 * Keelway Client SDK — Stable Typed Errors and Error Codes.
 *
 * Mirrors `core/sdk/errors.py` and `core/sdk/client.py::_handle_response_error`
 * word-for-word for deterministic cross-language error handling.
 */

export type ErrorDetails = Record<string, unknown>;

function resolveErrorInit(
  defaultCode: string,
  codeOrDetails?: string | ErrorDetails,
  details?: ErrorDetails,
): { code: string; details: ErrorDetails } {
  if (typeof codeOrDetails === "string") {
    return {
      code: codeOrDetails || defaultCode,
      details: details ? { ...details } : {},
    };
  }
  if (codeOrDetails && typeof codeOrDetails === "object") {
    return {
      code: defaultCode,
      details: { ...codeOrDetails },
    };
  }
  return {
    code: defaultCode,
    details: details ? { ...details } : {},
  };
}

/**
 * Base exception for all Keelway SDK errors.
 */
export class KeelwayError extends Error {
  public readonly code: string;
  public readonly details: ErrorDetails;
  public readonly status?: number;

  constructor(
    message: string,
    codeOrDetails?: string | ErrorDetails,
    details?: ErrorDetails,
    defaultCode = "KEELWAY_ERROR",
  ) {
    super(message);
    this.name = new.target.name;
    const resolved = resolveErrorInit(defaultCode, codeOrDetails, details);
    this.code = resolved.code;
    this.details = resolved.details;
    if (typeof this.details.status === "number") {
      this.status = this.details.status;
    }
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Raised when authentication fails or bearer token is missing/invalid (HTTP 401).
 */
export class AuthenticationError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "AUTHENTICATION_FAILED");
  }
}

/**
 * Raised when RBAC or policy rejects the requested action (HTTP 403).
 */
export class PermissionDeniedError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "PERMISSION_DENIED");
  }
}

/**
 * Raised when a mutation or request violates sovereign or workspace policy (HTTP 422).
 */
export class PolicyViolationError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "POLICY_VIOLATION");
  }
}

/**
 * Raised when a task, response, model, or tenant resource is not found (HTTP 404).
 */
export class TaskNotFoundError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "TASK_NOT_FOUND");
  }
}

/**
 * Raised when an operation attempts external egress under Air-Gap / zero-egress isolation (HTTP 403).
 */
export class AirGapEgressError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "AIRGAP_EGRESS_BLOCKED");
  }
}

/**
 * Raised when an enterprise action requires independent dual-human signoffs (HTTP 403).
 */
export class QuorumRequiredError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "QUORUM_APPROVAL_PENDING");
  }
}

/**
 * Raised when a flight tape replay, seal, or fork operation fails.
 */
export class FlightRecorderError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "FLIGHT_RECORDER_ERROR");
  }
}

/**
 * Raised when tenant or request spend cap / budget is exceeded (HTTP 402).
 */
export class BudgetExceededError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "BUDGET_EXCEEDED");
  }
}

/**
 * Raised when tenant or provider rate limits are exceeded (HTTP 429).
 */
export class RateLimitExceededError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "RATE_LIMIT_EXCEEDED");
  }
}

/**
 * Raised when the Keelway daemon is unreachable or the request times out.
 */
export class ConnectionError extends KeelwayError {
  constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails) {
    super(message, codeOrDetails, details, "DAEMON_UNREACHABLE");
  }
}

/**
 * Extracts a human-readable error message from a parsed JSON body or raw response text.
 */
function extractErrorDetail(body: unknown): string {
  if (body === null || body === undefined) {
    return "";
  }
  if (typeof body === "string") {
    const trimmed = body.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        const parsed: unknown = JSON.parse(trimmed);
        return extractErrorDetail(parsed);
      } catch {
        return body;
      }
    }
    return body;
  }
  if (typeof body === "object") {
    const record = body as Record<string, unknown>;
    if ("detail" in record && record.detail !== undefined && record.detail !== null) {
      return typeof record.detail === "string"
        ? record.detail
        : JSON.stringify(record.detail);
    }
    if (
      "error" in record &&
      record.error &&
      typeof record.error === "object" &&
      "message" in (record.error as Record<string, unknown>)
    ) {
      return String((record.error as Record<string, unknown>).message);
    }
    if ("reason" in record && typeof record.reason === "string") {
      return record.reason;
    }
    if ("message" in record && typeof record.message === "string") {
      return record.message;
    }
    return JSON.stringify(record);
  }
  return String(body);
}

/**
 * Translates HTTP error status codes and payloads into typed `KeelwayError` subclasses,
 * matching `core/sdk/client.py::_handle_response_error` word-for-word.
 */
export function mapHttpError(
  status: number,
  body: unknown,
  extraDetails?: ErrorDetails,
): KeelwayError {
  const msg = extractErrorDetail(body);
  const details: ErrorDetails = { status, ...(extraDetails ?? {}) };

  if (status === 401) {
    return new AuthenticationError(`Authentication failed: ${msg}`, details);
  }
  if (status === 402) {
    return new BudgetExceededError(`Budget exceeded: ${msg}`, details);
  }
  if (status === 403) {
    const lower = msg.toLowerCase();
    if (lower.includes("air-gap") || lower.includes("air_gap") || lower.includes("egress")) {
      return new AirGapEgressError(`Air-Gap zero-egress violation: ${msg}`, details);
    }
    if (lower.includes("quorum")) {
      return new QuorumRequiredError(`Dual-human quorum required: ${msg}`, details);
    }
    return new PermissionDeniedError(`Permission denied: ${msg}`, details);
  }
  if (status === 404) {
    return new TaskNotFoundError(`Resource not found: ${msg}`, details);
  }
  if (status === 422) {
    return new PolicyViolationError(`Policy validation failed: ${msg}`, details);
  }
  if (status === 429) {
    return new RateLimitExceededError(`Rate limit exceeded: ${msg}`, details);
  }
  return new KeelwayError(`HTTP ${status}: ${msg}`, details);
}
