from __future__ import annotations

from aip.integration.folderwatch.contracts.file_request import FileRequest
from aip.integration.validation.validator import ValidationIssue, ValidationResult, Validator


class FileValidator(Validator):
    """Validates folder watch file requests with generic rules."""

    def validate(self, payload: object) -> ValidationResult:
        if not isinstance(payload, FileRequest):
            return ValidationResult(ok=False, issues=[ValidationIssue(field="payload", message="payload is required")])
        issues: list[ValidationIssue] = []
        if not payload.path:
            issues.append(ValidationIssue(field="path", message="path is required"))
        if not payload.filename:
            issues.append(ValidationIssue(field="filename", message="filename is required"))
        if not payload.extension:
            issues.append(ValidationIssue(field="extension", message="extension is required"))
        if payload.size <= 0:
            issues.append(ValidationIssue(field="size", message="size must be greater than zero"))
        if issues:
            return ValidationResult(ok=False, issues=issues)
        return ValidationResult(ok=True, issues=[])
