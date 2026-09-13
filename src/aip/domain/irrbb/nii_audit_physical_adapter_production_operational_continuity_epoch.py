from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)


class NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError(ValueError):
    """Raised when a post-recovery operational continuity epoch cannot be recorded safely."""


class NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement(str, Enum):
    """Evidence required before a new post-recovery operational epoch may be recorded."""

    RECOVERY_ACCEPTANCE_VERIFIED = "RECOVERY_ACCEPTANCE_VERIFIED"
    PREVIOUS_STEADY_STATE_IDENTITY_VERIFIED = "PREVIOUS_STEADY_STATE_IDENTITY_VERIFIED"
    SERVICE_OWNERSHIP_RECONFIRMED = "SERVICE_OWNERSHIP_RECONFIRMED"
    CONTINUOUS_OBSERVABILITY_OWNERSHIP_RECONFIRMED = (
        "CONTINUOUS_OBSERVABILITY_OWNERSHIP_RECONFIRMED"
    )
    INCIDENT_ESCALATION_OWNERSHIP_RECONFIRMED = "INCIDENT_ESCALATION_OWNERSHIP_RECONFIRMED"
    CONTINUITY_RECOVERY_OWNERSHIP_RECONFIRMED = "CONTINUITY_RECOVERY_OWNERSHIP_RECONFIRMED"
    CHANGE_MANAGEMENT_OWNERSHIP_RECONFIRMED = "CHANGE_MANAGEMENT_OWNERSHIP_RECONFIRMED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_CONTINUITY_EPOCH_REQUIREMENTS = (
    frozenset(NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement)
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence:
    """Traceable source-neutral evidence for one continuity-epoch requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit operational continuity epoch evidence source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch:
    """Positive-only record opening one new steady-state epoch after accepted recovery."""

    recovery_acceptance: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance
    epoch_reference: str
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence, ...]

    def __post_init__(self) -> None:
        if (
            self.recovery_acceptance.recovery_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
        ):
            raise ValueError(
                "NII audit operational continuity epoch requires a successful recovery receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
            for result in self.recovery_acceptance.recovery_receipt.checkpoint_results
        ):
            raise ValueError(
                "NII audit operational continuity epoch requires every recovery checkpoint to succeed"
            )
        if not self.epoch_reference.strip():
            raise ValueError("NII audit operational continuity epoch_reference is required")
        if self.epoch_reference == self.recovery_acceptance.operations_reference:
            raise ValueError(
                "NII audit operational continuity epoch_reference must differ from the previous "
                "steady-state operations_reference"
            )

        requirements = tuple(item.requirement for item in self.evidence)
        if len(requirements) != len(set(requirements)):
            raise ValueError(
                "Duplicate NII audit operational continuity epoch evidence requirement"
            )
        if (
            frozenset(requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_CONTINUITY_EPOCH_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit operational continuity epoch evidence must cover every required control"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit operational continuity epoch evidence must be canonicalized"
            )

    @property
    def recovery_acceptance_reference(self) -> str:
        return self.recovery_acceptance.acceptance_reference

    @property
    def recovery_receipt_reference(self) -> str:
        return self.recovery_acceptance.recovery_receipt_reference

    @property
    def recovery_reference(self) -> str:
        return self.recovery_acceptance.recovery_reference

    @property
    def recovery_authorization_reference(self) -> str:
        return self.recovery_acceptance.recovery_authorization_reference

    @property
    def recovery_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.recovery_acceptance.recovery_action

    @property
    def intervention_acceptance_reference(self) -> str:
        return self.recovery_acceptance.intervention_acceptance_reference

    @property
    def intervention_receipt_reference(self) -> str:
        return self.recovery_acceptance.intervention_receipt_reference

    @property
    def intervention_reference(self) -> str:
        return self.recovery_acceptance.intervention_reference

    @property
    def intervention_authorization_reference(self) -> str:
        return self.recovery_acceptance.intervention_authorization_reference

    @property
    def intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.recovery_acceptance.intervention_action

    @property
    def attestation_reference(self) -> str:
        return self.recovery_acceptance.attestation_reference

    @property
    def previous_operations_reference(self) -> str:
        return self.recovery_acceptance.operations_reference

    @property
    def adapter_reference(self) -> str:
        return self.recovery_acceptance.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.recovery_acceptance.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.recovery_acceptance.artifact_reference
