from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from aip.integration.contracts.validation import ValidationPipeline


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A single validation issue collected by the pipeline."""

    field: str
    message: str
    valid: bool = False


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of a validation pass."""

    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class Validator(ValidationPipeline):
    """Reusable validation pipeline with no institution-specific rules."""

    def validate(
        self,
        payload: Any,
        rules: Sequence[Callable[[Any], tuple[bool, str | None]]] | None = None,
    ) -> ValidationResult:
        if payload is None:
            return ValidationResult(
                ok=False, issues=[ValidationIssue(field="payload", message="payload is required")]
            )

        issues: list[ValidationIssue] = []
        if rules is not None:
            for rule in rules:
                is_valid, message = rule(payload)
                if not is_valid and message:
                    issues.append(ValidationIssue(field="payload", message=message))

        if not issues:
            if isinstance(payload, dict):
                return ValidationResult(ok=True, issues=[], details={"payload": payload})
            return ValidationResult(ok=True, issues=[], details={"payload": payload})

        return ValidationResult(ok=False, issues=issues, details={"payload": payload})
