from __future__ import annotations

from aip.integration.validation.validator import ValidationIssue, ValidationResult, Validator
from aip.integration.sqlserver.contracts.sql_request import SQLRequest


class SQLValidator(Validator):
    """Validation rules for SQL Server requests."""

    def validate(self, payload: object) -> ValidationResult:
        if not isinstance(payload, SQLRequest):
            return ValidationResult(ok=False, issues=[ValidationIssue(field="payload", message="payload must be SQLRequest")])

        issues: list[ValidationIssue] = []
        if not payload.query_name.strip():
            issues.append(ValidationIssue(field="query_name", message="query_name is required"))
        if not payload.query_text.strip():
            issues.append(ValidationIssue(field="query_text", message="query_text is required"))
        if payload.parameters is None:
            issues.append(ValidationIssue(field="parameters", message="parameters must not be null"))
        if payload.page_size <= 0:
            issues.append(ValidationIssue(field="page_size", message="page_size must be positive"))

        return ValidationResult(ok=not issues, issues=issues, details={"query_name": payload.query_name})
