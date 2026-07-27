from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Structured context for AIP exceptions."""

    code: str
    details: Mapping[str, Any]


class AIPError(Exception):
    """Base exception for controlled AIP errors."""

    default_code = "AIP_ERROR"

    def __init__(self, message: str, *, code: str | None = None, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = ErrorContext(code=code or self.default_code, details=dict(details or {}))

    @property
    def code(self) -> str:
        return self.context.code

    @property
    def details(self) -> Mapping[str, Any]:
        return self.context.details

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ValidationError(AIPError):
    default_code = "VALIDATION_ERROR"


class ConfigurationError(AIPError):
    default_code = "CONFIGURATION_ERROR"


class InfrastructureError(AIPError):
    default_code = "INFRASTRUCTURE_ERROR"


class NotFoundError(AIPError):
    default_code = "NOT_FOUND"


class ConflictError(AIPError):
    default_code = "CONFLICT"


class UnauthorizedError(AIPError):
    default_code = "UNAUTHORIZED"
