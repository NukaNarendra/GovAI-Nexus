from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class EnterprisePlatformError(Exception):
    def __init__(
        self,
        message: str,
        internal_code: str,
        severity: str = "ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.internal_code = internal_code
        self.severity = severity
        self.details = details or {}


class DomainLogicError(EnterprisePlatformError):
    def __init__(
        self, message: str, internal_code: str, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, internal_code, "ERROR", details)


class SecurityError(EnterprisePlatformError):
    def __init__(
        self, message: str, internal_code: str, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, internal_code, "CRITICAL", details)


class InfrastructureError(EnterprisePlatformError):
    def __init__(
        self, message: str, internal_code: str, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, internal_code, "CRITICAL", details)


class ComplianceViolationError(DomainLogicError):
    def __init__(
        self, message: str, violations: list, details: Optional[Dict[str, Any]] = None
    ):
        payload = details or {}
        payload["violations"] = violations
        super().__init__(message, "ERR_COMP_001", payload)


class RiskThresholdExceededError(DomainLogicError):
    def __init__(
        self,
        current_score: float,
        threshold: float,
        details: Optional[Dict[str, Any]] = None,
    ):
        msg = f"Risk score {current_score} exceeds strict threshold {threshold}"
        super().__init__(msg, "ERR_RISK_001", details)


class AIOrchestrationError(DomainLogicError):
    def __init__(
        self, message: str, agent_id: str, details: Optional[Dict[str, Any]] = None
    ):
        payload = details or {}
        payload["agent_id"] = agent_id
        super().__init__(message, "ERR_AI_001", payload)


class LLMProviderOutageError(InfrastructureError):
    def __init__(self, provider: str, details: Optional[Dict[str, Any]] = None):
        msg = f"LLM Provider {provider} is currently experiencing an outage or severe degradation."
        super().__init__(msg, "ERR_INF_LLM_001", details)


class DatabaseTransactionError(InfrastructureError):
    def __init__(self, operation: str, details: Optional[Dict[str, Any]] = None):
        msg = f"Database transaction failed during operation: {operation}"
        super().__init__(msg, "ERR_INF_DB_001", details)


class HITLTaskLockedError(DomainLogicError):
    def __init__(
        self, task_id: str, current_owner: str, details: Optional[Dict[str, Any]] = None
    ):
        msg = f"HITL Task {task_id} is currently locked and claimed by user {current_owner}."
        super().__init__(msg, "ERR_HITL_001", details)


class WORMStorageCompromisedError(SecurityError):
    def __init__(
        self, corrupted_records: list, details: Optional[Dict[str, Any]] = None
    ):
        msg = "CRITICAL: WORM Storage cryptographic chain validation failed. Data tampering detected."
        payload = details or {}
        payload["corrupted_record_ids"] = corrupted_records
        super().__init__(msg, "ERR_SEC_WORM_001", payload)


class InsufficientPermissionsError(SecurityError):
    def __init__(self, required_role: str, details: Optional[Dict[str, Any]] = None):
        msg = f"Operation requires role: {required_role}"
        super().__init__(msg, "ERR_SEC_AUTH_001", details)


def map_domain_error_to_http(error: EnterprisePlatformError) -> HTTPException:
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    if isinstance(error, ComplianceViolationError) or isinstance(
        error, RiskThresholdExceededError
    ):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(error, SecurityError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(error, HITLTaskLockedError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(error, LLMProviderOutageError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HTTPException(
        status_code=status_code,
        detail={
            "message": error.message,
            "internal_code": error.internal_code,
            "severity": error.severity,
            "details": error.details,
        },
    )


def handle_validation_exception(errors: list) -> HTTPException:
    formatted_errors = []
    for err in errors:
        formatted_errors.append(
            {
                "location": " -> ".join([str(loc) for loc in err.get("loc", [])]),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": "Payload validation failed",
            "internal_code": "ERR_VAL_001",
            "errors": formatted_errors,
        },
    )
