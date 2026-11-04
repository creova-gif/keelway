"""Keelway Client SDK — Stable Typed Errors and Error Codes."""
from typing import Optional, Dict, Any


class KeelwayError(Exception):
    """Base exception for all Keelway SDK errors."""
    code: str = "KEELWAY_ERROR"

    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.details = details or {}

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} code={self.code} message={self.message!r}>"


class AuthenticationError(KeelwayError):
    """Raised when authentication fails or token is missing/invalid."""
    code = "AUTHENTICATION_FAILED"


class PermissionDeniedError(KeelwayError):
    """Raised when RBAC or policy rejects the requested action."""
    code = "PERMISSION_DENIED"


class PolicyViolationError(KeelwayError):
    """Raised when a mutation violates sovereign or workspace policy."""
    code = "POLICY_VIOLATION"


class TaskNotFoundError(KeelwayError):
    """Raised when a task or run is not found."""
    code = "TASK_NOT_FOUND"


class AirGapEgressError(KeelwayError):
    """Raised when an operation attempts external egress under Air-Gap isolation."""
    code = "AIRGAP_EGRESS_BLOCKED"


class QuorumRequiredError(KeelwayError):
    """Raised when an enterprise action requires independent dual-human signoffs."""
    code = "QUORUM_APPROVAL_PENDING"


class FlightRecorderError(KeelwayError):
    """Raised when a flight tape replay, seal, or fork operation fails."""
    code = "FLIGHT_RECORDER_ERROR"


class ConnectionError(KeelwayError):
    """Raised when the Keelway local daemon is unreachable."""
    code = "DAEMON_UNREACHABLE"
