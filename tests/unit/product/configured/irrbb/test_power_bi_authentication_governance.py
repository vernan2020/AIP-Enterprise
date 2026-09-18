from __future__ import annotations

import json

import pytest

from aip.product.configured.irrbb.power_bi_authentication_governance import (
    POWER_BI_AUTHENTICATION_GOVERNANCE_REPORT_TYPE,
    POWER_BI_AUTHENTICATION_GOVERNANCE_REPORT_VERSION,
    PowerBIAuthenticationGovernanceEvidenceValidator,
    PowerBIInteractiveAuthenticationPolicy,
)


def _payload() -> dict[str, object]:
    return {
        "report_type": POWER_BI_AUTHENTICATION_GOVERNANCE_REPORT_TYPE,
        "report_version": POWER_BI_AUTHENTICATION_GOVERNANCE_REPORT_VERSION,
        "authentication_mode": "institutionally-approved-mode",
        "identity_or_application_pattern": "institutionally-approved-identity-pattern",
        "permitted_api_permissions": ["approved.permission"],
        "credential_storage_mechanism": "institutionally-approved-storage",
        "token_lifecycle_policy": "institutionally-approved-lifecycle",
        "interactive_authentication_policy": "PROHIBITED",
        "authentication_profile_key_owner": "institutionally-approved-runtime-owner",
        "authorized_deployment_environments": ["production"],
    }


def test_validator_accepts_complete_provider_agnostic_governance_evidence() -> None:
    evidence = PowerBIAuthenticationGovernanceEvidenceValidator().parse_json_document(
        json.dumps(_payload())
    )

    assert evidence.authentication_mode == "institutionally-approved-mode"
    assert evidence.identity_or_application_pattern == (
        "institutionally-approved-identity-pattern"
    )
    assert evidence.permitted_api_permissions == ("approved.permission",)
    assert (
        evidence.interactive_authentication_policy
        is PowerBIInteractiveAuthenticationPolicy.PROHIBITED
    )
    assert evidence.authorized_deployment_environments == ("production",)


def test_safe_summary_does_not_echo_authentication_governance_details() -> None:
    validator = PowerBIAuthenticationGovernanceEvidenceValidator()
    payload = _payload()
    evidence = validator.validate_report(payload)

    summary = validator.safe_validation_summary(evidence)
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["validation_status"] == "VALIDATED_GOVERNANCE_EVIDENCE"
    assert summary["required_decision_count"] == 8
    assert summary["permitted_api_permission_count"] == 1
    assert summary["authorized_deployment_environment_count"] == 1
    assert summary["authentication_provider_implementation_authorized"] is False
    assert summary["production_activation_authorized"] is False

    for field in (
        "institutionally-approved-mode",
        "institutionally-approved-identity-pattern",
        "approved.permission",
        "institutionally-approved-storage",
        "institutionally-approved-lifecycle",
        "institutionally-approved-runtime-owner",
        "production",
    ):
        assert field not in serialized


def test_missing_governance_decision_fails_closed() -> None:
    payload = _payload()
    del payload["token_lifecycle_policy"]

    with pytest.raises(ValueError, match="missing=.*token_lifecycle_policy"):
        PowerBIAuthenticationGovernanceEvidenceValidator().validate_report(payload)


def test_unknown_secret_like_field_is_rejected_without_echoing_value() -> None:
    payload = _payload()
    payload["access_token"] = "must-never-be-accepted"

    with pytest.raises(ValueError, match=r"unknown=\['access_token'\]") as exc_info:
        PowerBIAuthenticationGovernanceEvidenceValidator().validate_report(payload)

    assert "must-never-be-accepted" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("permitted_api_permissions", []),
        ("authorized_deployment_environments", []),
        ("permitted_api_permissions", ["same", "SAME"]),
        ("authorized_deployment_environments", ["prod", "PROD"]),
    ],
)
def test_required_arrays_must_be_nonempty_and_unique(
    field_name: str,
    value: list[str],
) -> None:
    payload = _payload()
    payload[field_name] = value

    with pytest.raises(ValueError):
        PowerBIAuthenticationGovernanceEvidenceValidator().validate_report(payload)


def test_interactive_authentication_policy_is_explicit_and_closed_enum() -> None:
    payload = _payload()
    payload["interactive_authentication_policy"] = "UNDECIDED"

    with pytest.raises(ValueError, match="must be PROHIBITED or PERMITTED"):
        PowerBIAuthenticationGovernanceEvidenceValidator().validate_report(payload)


def test_report_contract_rejects_wrong_type_or_version() -> None:
    wrong_type = _payload()
    wrong_type["report_type"] = "OTHER"
    with pytest.raises(ValueError, match="unsupported.*report_type"):
        PowerBIAuthenticationGovernanceEvidenceValidator().validate_report(wrong_type)

    wrong_version = _payload()
    wrong_version["report_version"] = "1900.01.01"
    with pytest.raises(ValueError, match="unsupported.*report_version"):
        PowerBIAuthenticationGovernanceEvidenceValidator().validate_report(wrong_version)
