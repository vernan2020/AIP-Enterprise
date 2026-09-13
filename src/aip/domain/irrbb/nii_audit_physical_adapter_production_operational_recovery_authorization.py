from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError(ValueError):
    """Raised when operational recovery authorization cannot be issued safely."""


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction(str, Enum):
    """Explicit governed return-to-service action after an accepted intervention."""

    RESUME = "RESUME"
    REACTIVATE = "REACTIVATE"


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement(str, Enum):
    """Evidence required before return-to-service may be authorized."""

    INTERVENTION_ACCEPTANCE_VERIFIED = "INTERVENTION_ACCEPTANCE_VERIFIED"
    RECOVERY_POLICY_VERIFIED = "RECOVERY_POLICY_VERIFIED"
    RECOVERY_READINESS_CONFIRMED = "RECOVERY_READINESS_CONFIRMED"
    OPERATIONS_RECOVERY_AUTHORITY_CONFIRMED = "OPERATIONS_RECOVERY_AUTHORITY_CONFIRMED"
    CONTINUITY_PROTECTION_CONFIRMED = "CONTINUITY_PROTECTION_CONFIRMED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_REQUIREMENTS = frozenset(
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence:
    """Traceable source-neutral evidence for one recovery-authorization requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError("NII audit operational recovery evidence source_reference is required")


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization:
    """Positive-only authorization for one exact return-to-service action."""

    intervention_acceptance: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance
    authorization_reference: str
    action: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence, ...]

    def __post_init__(self) -> None:
        if not self.authorization_reference.strip():
            raise ValueError("NII audit operational recovery authorization_reference is required")

        expected_action = {
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND: (
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
            ),
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.DEACTIVATE: (
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.REACTIVATE
            ),
        }[self.intervention_acceptance.action]
        if self.action is not expected_action:
            raise ValueError(
                "NII audit operational recovery action must match the accepted intervention action"
            )

        requirements = tuple(item.requirement for item in self.evidence)
        if len(requirements) != len(set(requirements)):
            raise ValueError("Duplicate NII audit operational recovery evidence requirement")
        if (
            frozenset(requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit operational recovery evidence must cover every required control"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError("NII audit operational recovery evidence must be canonicalized")

    @property
    def intervention_acceptance_reference(self) -> str:
        return self.intervention_acceptance.acceptance_reference

    @property
    def intervention_receipt_reference(self) -> str:
        return self.intervention_acceptance.intervention_receipt_reference

    @property
    def intervention_reference(self) -> str:
        return self.intervention_acceptance.intervention_reference

    @property
    def intervention_authorization_reference(self) -> str:
        return self.intervention_acceptance.authorization_reference

    @property
    def intervention_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.intervention_acceptance.action

    @property
    def attestation_reference(self) -> str:
        return self.intervention_acceptance.attestation_reference

    @property
    def operations_reference(self) -> str:
        return self.intervention_acceptance.operations_reference

    @property
    def adapter_reference(self) -> str:
        return self.intervention_acceptance.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.intervention_acceptance.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.intervention_acceptance.artifact_reference
