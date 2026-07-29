from __future__ import annotations

from datetime import datetime

from aip.integration.bccr.contracts.request import BCCRRequest
from aip.integration.bccr.contracts.response import BCCRResponse
from aip.integration.validation.validator import ValidationIssue, ValidationResult, Validator


class ResponseValidator(Validator):
    """Validates BCCR requests and response payloads."""

    def validate(self, payload: object) -> ValidationResult:
        if isinstance(payload, BCCRRequest):
            issues: list[ValidationIssue] = []
            if not payload.indicator_codes:
                issues.append(ValidationIssue(field="indicator_codes", message="indicator_codes is required"))
            if not payload.from_date:
                issues.append(ValidationIssue(field="from_date", message="from_date is required"))
            if not payload.to_date:
                issues.append(ValidationIssue(field="to_date", message="to_date is required"))
            if issues:
                return ValidationResult(ok=False, issues=issues)
            return ValidationResult(ok=True, issues=[])

        if isinstance(payload, BCCRResponse):
            response_issues: list[ValidationIssue] = []
            if not payload.indicator_code:
                response_issues.append(ValidationIssue(field="indicator_code", message="indicator_code is required"))
            try:
                datetime.fromisoformat(payload.observation_date.replace("Z", "+00:00"))
            except ValueError:
                response_issues.append(ValidationIssue(field="observation_date", message="observation_date is invalid"))
            if response_issues:
                return ValidationResult(ok=False, issues=response_issues)
            return ValidationResult(ok=True, issues=[])

        return ValidationResult(ok=False, issues=[ValidationIssue(field="payload", message="payload is required")])
