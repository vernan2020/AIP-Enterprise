from __future__ import annotations

import json

import pytest

from aip.product.configured.irrbb.borrowing_governance import (
    BORROWING_GOVERNANCE_REPORT_TYPE,
    BORROWING_GOVERNANCE_REPORT_VERSION,
    BorrowingGovernanceEvidenceValidator,
)


def _payload() -> dict[str, object]:
    return {
        "report_type": BORROWING_GOVERNANCE_REPORT_TYPE,
        "report_version": BORROWING_GOVERNANCE_REPORT_VERSION,
        "operation_identity_policy": "institutionally-approved-operation-identity-policy",
        "currency_derivation_policy": "institutionally-approved-currency-policy",
        "rate_type_policy": "institutionally-approved-rate-type-policy",
        "reference_rate_policy": "institutionally-approved-reference-rate-policy",
        "payment_frequency_policy": "institutionally-approved-payment-frequency-policy",
        "row_level_reconciliation_policy": "institutionally-approved-reconciliation-policy",
    }


def test_complete_governance_evidence_validates_without_authorizing_runtime() -> None:
    validator = BorrowingGovernanceEvidenceValidator()
    evidence = validator.validate_report(_payload())

    summary = validator.safe_validation_summary(evidence)

    assert summary["validation_status"] == "VALIDATED_GOVERNANCE_EVIDENCE"
    assert summary["required_decision_count"] == 6
    assert summary["validated_decision_count"] == 6
    assert summary["canonical_mapper_implementation_authorized"] is False
    assert summary["contractual_row_extraction_authorized"] is False
    assert summary["production_activation_authorized"] is False

    serialized = json.dumps(summary, sort_keys=True)
    for semantic_value in (
        "institutionally-approved-operation-identity-policy",
        "institutionally-approved-currency-policy",
        "institutionally-approved-rate-type-policy",
        "institutionally-approved-reference-rate-policy",
        "institutionally-approved-payment-frequency-policy",
        "institutionally-approved-reconciliation-policy",
    ):
        assert semantic_value not in serialized


@pytest.mark.parametrize(
    "missing_field",
    (
        "operation_identity_policy",
        "currency_derivation_policy",
        "rate_type_policy",
        "reference_rate_policy",
        "payment_frequency_policy",
        "row_level_reconciliation_policy",
    ),
)
def test_missing_required_governance_decision_fails_closed(missing_field: str) -> None:
    payload = _payload()
    payload.pop(missing_field)

    with pytest.raises(ValueError, match="invalid shape"):
        BorrowingGovernanceEvidenceValidator().validate_report(payload)


def test_unknown_governance_field_fails_closed() -> None:
    payload = _payload()
    payload["inferred_currency_default"] = "CRC"

    with pytest.raises(ValueError, match="unknown"):
        BorrowingGovernanceEvidenceValidator().validate_report(payload)


@pytest.mark.parametrize(
    "field_name",
    (
        "operation_identity_policy",
        "currency_derivation_policy",
        "rate_type_policy",
        "reference_rate_policy",
        "payment_frequency_policy",
        "row_level_reconciliation_policy",
    ),
)
def test_blank_or_untrimmed_decisions_are_rejected(field_name: str) -> None:
    payload = _payload()
    payload[field_name] = "  "

    with pytest.raises(ValueError, match=field_name):
        BorrowingGovernanceEvidenceValidator().validate_report(payload)

    payload = _payload()
    payload[field_name] = " value "

    with pytest.raises(ValueError, match=field_name):
        BorrowingGovernanceEvidenceValidator().validate_report(payload)


def test_json_parser_requires_object_root_and_valid_json() -> None:
    validator = BorrowingGovernanceEvidenceValidator()

    with pytest.raises(ValueError, match="not valid JSON"):
        validator.parse_json_document("{")

    with pytest.raises(ValueError, match="root must be an object"):
        validator.parse_json_document("[]")


def test_report_type_and_version_are_exact_contracts() -> None:
    payload = _payload()
    payload["report_type"] = "OTHER"
    with pytest.raises(ValueError, match="report_type"):
        BorrowingGovernanceEvidenceValidator().validate_report(payload)

    payload = _payload()
    payload["report_version"] = "2026.09.17"
    with pytest.raises(ValueError, match="report_version"):
        BorrowingGovernanceEvidenceValidator().validate_report(payload)
