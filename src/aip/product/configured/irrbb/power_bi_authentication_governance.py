from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

POWER_BI_AUTHENTICATION_GOVERNANCE_REPORT_TYPE = (
    "IRRBB_POWER_BI_AUTHENTICATION_GOVERNANCE_EVIDENCE"
)
POWER_BI_AUTHENTICATION_GOVERNANCE_REPORT_VERSION = "2026.09.18"

_REPORT_KEYS = frozenset(
    {
        "report_type",
        "report_version",
        "authentication_mode",
        "identity_or_application_pattern",
        "permitted_api_permissions",
        "credential_storage_mechanism",
        "token_lifecycle_policy",
        "interactive_authentication_policy",
        "authentication_profile_key_owner",
        "authorized_deployment_environments",
    }
)


class PowerBIInteractiveAuthenticationPolicy(str, Enum):
    """Institutionally documented policy for interactive Power BI authentication."""

    PROHIBITED = "PROHIBITED"
    PERMITTED = "PERMITTED"


@dataclass(frozen=True, slots=True)
class PowerBIAuthenticationGovernanceEvidence:
    """Provider-agnostic record of the eight external authentication decisions.

    This evidence documents governance inputs only. It does not contain credentials,
    choose an authentication implementation, authorize contractual row extraction, or
    authorize production RTILB activation.
    """

    authentication_mode: str
    identity_or_application_pattern: str
    permitted_api_permissions: tuple[str, ...]
    credential_storage_mechanism: str
    token_lifecycle_policy: str
    interactive_authentication_policy: PowerBIInteractiveAuthenticationPolicy
    authentication_profile_key_owner: str
    authorized_deployment_environments: tuple[str, ...]


class PowerBIAuthenticationGovernanceEvidenceValidator:
    """Validate exact, non-secret Power BI authentication-governance evidence."""

    def parse_json_document(self, document: str) -> PowerBIAuthenticationGovernanceEvidence:
        """Parse one complete governance-evidence JSON document."""

        try:
            payload = json.loads(document)
        except json.JSONDecodeError as exc:
            raise ValueError("Power BI authentication governance evidence is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("Power BI authentication governance evidence root must be an object")
        return self.validate_report(payload)

    def validate_report(
        self,
        payload: dict[str, Any],
    ) -> PowerBIAuthenticationGovernanceEvidence:
        """Validate exact report shape and the eight required governance decisions."""

        self._require_exact_keys(payload)
        report_type = self._require_text(payload["report_type"], "report_type")
        if report_type != POWER_BI_AUTHENTICATION_GOVERNANCE_REPORT_TYPE:
            raise ValueError("unsupported Power BI authentication governance report_type")

        report_version = self._require_text(payload["report_version"], "report_version")
        if report_version != POWER_BI_AUTHENTICATION_GOVERNANCE_REPORT_VERSION:
            raise ValueError("unsupported Power BI authentication governance report_version")

        try:
            interactive_policy = PowerBIInteractiveAuthenticationPolicy(
                self._require_text(
                    payload["interactive_authentication_policy"],
                    "interactive_authentication_policy",
                )
            )
        except ValueError as exc:
            raise ValueError(
                "interactive_authentication_policy must be PROHIBITED or PERMITTED"
            ) from exc

        return PowerBIAuthenticationGovernanceEvidence(
            authentication_mode=self._require_text(
                payload["authentication_mode"],
                "authentication_mode",
            ),
            identity_or_application_pattern=self._require_text(
                payload["identity_or_application_pattern"],
                "identity_or_application_pattern",
            ),
            permitted_api_permissions=self._require_unique_text_array(
                payload["permitted_api_permissions"],
                "permitted_api_permissions",
            ),
            credential_storage_mechanism=self._require_text(
                payload["credential_storage_mechanism"],
                "credential_storage_mechanism",
            ),
            token_lifecycle_policy=self._require_text(
                payload["token_lifecycle_policy"],
                "token_lifecycle_policy",
            ),
            interactive_authentication_policy=interactive_policy,
            authentication_profile_key_owner=self._require_text(
                payload["authentication_profile_key_owner"],
                "authentication_profile_key_owner",
            ),
            authorized_deployment_environments=self._require_unique_text_array(
                payload["authorized_deployment_environments"],
                "authorized_deployment_environments",
            ),
        )

    @staticmethod
    def safe_validation_summary(
        evidence: PowerBIAuthenticationGovernanceEvidence,
    ) -> dict[str, object]:
        """Return a non-secret completeness summary without echoing governance details."""

        return {
            "report_type": "IRRBB_POWER_BI_AUTHENTICATION_GOVERNANCE_VALIDATION",
            "report_version": POWER_BI_AUTHENTICATION_GOVERNANCE_REPORT_VERSION,
            "validation_status": "VALIDATED_GOVERNANCE_EVIDENCE",
            "required_decision_count": 8,
            "permitted_api_permission_count": len(evidence.permitted_api_permissions),
            "authorized_deployment_environment_count": len(
                evidence.authorized_deployment_environments
            ),
            "authentication_provider_implementation_authorized": False,
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
            "Power BI authentication governance evidence has invalid shape: "
            + ", ".join(details)
        )

    @staticmethod
    def _require_text(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError(f"{field_name} must be nonblank trimmed text")
        return value

    @classmethod
    def _require_unique_text_array(
        cls,
        value: Any,
        field_name: str,
    ) -> tuple[str, ...]:
        if not isinstance(value, list) or not value:
            raise ValueError(f"{field_name} must be a non-empty array")
        values = tuple(
            cls._require_text(item, f"{field_name}[{index}]")
            for index, item in enumerate(value)
        )
        normalized = tuple(item.casefold() for item in values)
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"{field_name} must contain unique values ignoring case")
        return values
