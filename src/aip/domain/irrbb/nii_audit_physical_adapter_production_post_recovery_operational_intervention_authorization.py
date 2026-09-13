from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_reattestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionRequirement(str, Enum):
    """Evidence required before a post-recovery intervention may be authorized."""

    STATUS_REATTESTATION_VERIFIED = "STATUS_REATTESTATION_VERIFIED"
    CONTINUITY_EPOCH_VERIFIED = "CONTINUITY_EPOCH_VERIFIED"
    INTERVENTION_POLICY_VERIFIED = "INTERVENTION_POLICY_VERIFIED"
    OPERATIONAL_APPROVAL_VERIFIED = "OPERATIONAL_APPROVAL_VERIFIED"
    CONTINUITY_IMPACT_VERIFIED = "CONTINUITY_IMPACT_VERIFIED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_POST_RECOVERY_OPERATIONAL_INTERVENTION_REQUIREMENTS = frozenset(
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionRequirement
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
    ValueError
):
    """Raised when a post-recovery intervention authorization is inconsistent."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence:
    """Traceable source-neutral evidence for one post-recovery intervention control."""

    requirement: NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit post-recovery intervention evidence source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization:
    """Positive-only authorization bound to one exact non-healthy Phase 57 re-attestation."""

    operational_status_reattestation: (
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation
    )
    authorization_reference: str
    action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction
    evidence: tuple[
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence, ...
    ]

    def __post_init__(self) -> None:
        if not self.authorization_reference.strip():
            raise ValueError(
                "NII audit post-recovery intervention authorization_reference is required"
            )
        if not self.operational_status_reattestation.reattestation_reference.strip():
            raise ValueError(
                "NII audit post-recovery intervention requires a valid status re-attestation"
            )
        if (
            self.operational_status_reattestation.status
            is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
        ):
            raise ValueError(
                "HEALTHY NII audit post-recovery operational status cannot authorize intervention"
            )
        if not self.operational_status_reattestation.exception_references:
            raise ValueError(
                "Non-HEALTHY NII audit post-recovery operational status requires exceptions"
            )
        if not self.operational_status_reattestation.epoch_reference.strip():
            raise ValueError(
                "NII audit post-recovery intervention requires a valid continuity epoch"
            )
        if (
            self.operational_status_reattestation.epoch_reference
            == self.operational_status_reattestation.previous_operations_reference
        ):
            raise ValueError(
                "NII audit post-recovery intervention requires a distinct continuity epoch"
            )
        if (
            self.authorization_reference
            == self.operational_status_reattestation.intervention_authorization_reference
        ):
            raise ValueError(
                "NII audit post-recovery intervention cannot reuse the previous authorization_reference"
            )

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError("Duplicate NII audit post-recovery intervention evidence requirement")
        if (
            frozenset(evidence_requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_POST_RECOVERY_OPERATIONAL_INTERVENTION_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit post-recovery intervention evidence must cover every required control"
            )
        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError("NII audit post-recovery intervention evidence must be canonicalized")

    @property
    def reattestation_reference(self) -> str:
        return self.operational_status_reattestation.reattestation_reference

    @property
    def status(self) -> NIIRunAuditPhysicalAdapterProductionOperationalStatus:
        return self.operational_status_reattestation.status

    @property
    def epoch_reference(self) -> str:
        return self.operational_status_reattestation.epoch_reference

    @property
    def previous_operations_reference(self) -> str:
        return self.operational_status_reattestation.previous_operations_reference

    @property
    def previous_attestation_reference(self) -> str:
        return self.operational_status_reattestation.previous_attestation_reference

    @property
    def recovery_acceptance_reference(self) -> str:
        return self.operational_status_reattestation.recovery_acceptance_reference

    @property
    def recovery_receipt_reference(self) -> str:
        return self.operational_status_reattestation.recovery_receipt_reference

    @property
    def recovery_reference(self) -> str:
        return self.operational_status_reattestation.recovery_reference

    @property
    def recovery_authorization_reference(self) -> str:
        return self.operational_status_reattestation.recovery_authorization_reference

    @property
    def recovery_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.operational_status_reattestation.recovery_action

    @property
    def previous_intervention_authorization_reference(self) -> str:
        return self.operational_status_reattestation.intervention_authorization_reference

    @property
    def previous_intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.operational_status_reattestation.intervention_action

    @property
    def adapter_reference(self) -> str:
        return self.operational_status_reattestation.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.operational_status_reattestation.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.operational_status_reattestation.artifact_reference
