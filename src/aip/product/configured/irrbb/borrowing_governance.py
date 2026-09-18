from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

BORROWING_GOVERNANCE_REPORT_TYPE = "IRRBB_BORROWING_SOURCE_GOVERNANCE_EVIDENCE"
BORROWING_GOVERNANCE_REPORT_VERSION = "2026.09.18"

_REPORT_KEYS = frozenset(
    {
        "report_type",
        "report_version",
        "operation_identity_policy",
        "currency_derivation_policy",
        "rate_type_policy",
        "reference_rate_policy",
        "payment_frequency_policy",
        "row_level_reconciliation_policy",
    }
)


@dataclass(frozen=True, slots=True)
class BorrowingGovernanceEvidence:
    """Institutional decisions required before the borrowing adapter can be activated.

    The values are intentionally opaque governance statements. Validation proves
    completeness and shape only; it does not interpret the statements, create a
    canonical mapper, authorize row extraction, or authorize production RTILB.
    """

    operation_identity_policy: str
    currency_derivation_policy: str
    rate_type_policy: str
    reference_rate_policy: str
    payment_frequency_policy: str
    row_level_reconciliation_policy: str


class BorrowingGovernanceEvidenceValidator:
    """Validate exact, non-secret governance evidence for Obligaciones con Entidades."""

    def parse_json_document(self, document: str) -> BorrowingGovernanceEvidence:
        """Parse one complete governance-evidence JSON document."""

        try:
            payload = json.loads(document)
        except json.JSONDecodeError as exc:
            raise ValueError("borrowing governance evidence is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("borrowing governance evidence root must be an object")
        return self.validate_report(payload)

    def validate_report(self, payload: dict[str, Any]) -> BorrowingGovernanceEvidence:
        """Validate exact report shape and all six required institutional decisions."""

        self._require_exact_keys(payload)
        report_type = self._require_text(payload["report_type"], "report_type")
        if report_type != BORROWING_GOVERNANCE_REPORT_TYPE:
            raise ValueError("unsupported borrowing governance report_type")

        report_version = self._require_text(payload["report_version"], "report_version")
        if report_version != BORROWING_GOVERNANCE_REPORT_VERSION:
            raise ValueError("unsupported borrowing governance report_version")

        return BorrowingGovernanceEvidence(
            operation_identity_policy=self._require_text(
                payload["operation_identity_policy"],
                "operation_identity_policy",
            ),
            currency_derivation_policy=self._require_text(
                payload["currency_derivation_policy"],
                "currency_derivation_policy",
            ),
            rate_type_policy=self._require_text(
                payload["rate_type_policy"],
                "rate_type_policy",
            ),
            reference_rate_policy=self._require_text(
                payload["reference_rate_policy"],
                "reference_rate_policy",
            ),
            payment_frequency_policy=self._require_text(
                payload["payment_frequency_policy"],
                "payment_frequency_policy",
            ),
            row_level_reconciliation_policy=self._require_text(
                payload["row_level_reconciliation_policy"],
                "row_level_reconciliation_policy",
            ),
        )

    @staticmethod
    def safe_validation_summary(evidence: BorrowingGovernanceEvidence) -> dict[str, object]:
        """Return a completeness summary without echoing institutional semantics."""

        decisions = (
            evidence.operation_identity_policy,
            evidence.currency_derivation_policy,
            evidence.rate_type_policy,
            evidence.reference_rate_policy,
            evidence.payment_frequency_policy,
            evidence.row_level_reconciliation_policy,
        )
        return {
            "report_type": "IRRBB_BORROWING_SOURCE_GOVERNANCE_VALIDATION",
            "report_version": BORROWING_GOVERNANCE_REPORT_VERSION,
            "validation_status": "VALIDATED_GOVERNANCE_EVIDENCE",
            "required_decision_count": 6,
            "validated_decision_count": len(decisions),
            "canonical_mapper_implementation_authorized": False,
            "contractual_row_extraction_authorized": False,
            "production_activation_authorized": False,
        }

    @staticmethod
    def _require_exact_keys(payload: dict[str, Any]) -> None:
        actual = frozenset(payload)
        if actual == _REPORT_KEYS:
            return
        missing = sorted(_REPORT_KEYS - actual)
        unknown = sorted(actual - _REPORT_KEYS)
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if unknown:
            details.append(f"unknown={unknown}")
        raise ValueError(
            "borrowing governance evidence has invalid shape: " + ", ".join(details)
        )

    @staticmethod
    def _require_text(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError(f"{field_name} must be nonblank trimmed text")
        return value
