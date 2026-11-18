/**
 * Keelway Client SDK — Stable Typed Errors and Error Codes.
 *
 * Mirrors `core/sdk/errors.py` and `core/sdk/client.py::_handle_response_error`
 * word-for-word for deterministic cross-language error handling.
 */
export type ErrorDetails = Record<string, unknown>;
/**
 * Base exception for all Keelway SDK errors.
 */
export declare class KeelwayError extends Error {
    readonly code: string;
    readonly details: ErrorDetails;
    readonly status?: number;
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails, defaultCode?: string);
}
/**
 * Raised when authentication fails or bearer token is missing/invalid (HTTP 401).
 */
export declare class AuthenticationError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Raised when RBAC or policy rejects the requested action (HTTP 403).
 */
export declare class PermissionDeniedError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Raised when a mutation or request violates sovereign or workspace policy (HTTP 422).
 */
export declare class PolicyViolationError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Raised when a task, response, model, or tenant resource is not found (HTTP 404).
 */
export declare class TaskNotFoundError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Raised when an operation attempts external egress under Air-Gap / zero-egress isolation (HTTP 403).
 */
export declare class AirGapEgressError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Raised when an enterprise action requires independent dual-human signoffs (HTTP 403).
 */
export declare class QuorumRequiredError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Raised when a flight tape replay, seal, or fork operation fails.
 */
export declare class FlightRecorderError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Raised when tenant or request spend cap / budget is exceeded (HTTP 402).
 */
export declare class BudgetExceededError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Raised when tenant or provider rate limits are exceeded (HTTP 429).
 */
export declare class RateLimitExceededError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Raised when the Keelway daemon is unreachable or the request times out.
 */
export declare class ConnectionError extends KeelwayError {
    constructor(message: string, codeOrDetails?: string | ErrorDetails, details?: ErrorDetails);
}
/**
 * Translates HTTP error status codes and payloads into typed `KeelwayError` subclasses,
 * matching `core/sdk/client.py::_handle_response_error` word-for-word.
 */
export declare function mapHttpError(status: number, body: unknown, extraDetails?: ErrorDetails): KeelwayError;
//# sourceMappingURL=errors.d.ts.map