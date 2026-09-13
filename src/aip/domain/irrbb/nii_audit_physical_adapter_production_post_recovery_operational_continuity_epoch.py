from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_continuity_epoch import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_CONTINUITY_EPOCH_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError(
    ValueError
):
    """Raised when a new post-recovery continuity epoch cannot be recorded safely."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpoch:
    """Positive-only record opening a new steady-state epoch after Phase 63 acceptance."""

    recovery_acceptance: (
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance
    )
    epoch_reference: str
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence, ...]

    def __post_init__(self) -> None:
        if (
            self.recovery_acceptance.recovery_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
        ):
            raise ValueError(
                "NII audit post-recovery continuity epoch requires a successful recovery receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
            for result in self.recovery_acceptance.recovery_receipt.checkpoint_results
        ):
            raise ValueError(
                "NII audit post-recovery continuity epoch requires every recovery checkpoint to succeed"
            )
        if not self.epoch_reference.strip():
            raise ValueError("NII audit post-recovery continuity epoch_reference is required")
        if self.epoch_reference == self.recovery_acceptance.epoch_reference:
            raise ValueError(
                "NII audit post-recovery continuity epoch_reference must differ from the previous epoch_reference"
            )

        requirements = tuple(item.requirement for item in self.evidence)
        if len(requirements) != len(set(requirements)):
            raise ValueError("Duplicate NII audit post-recovery continuity epoch evidence requirement")
        if (
            frozenset(requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_CONTINUITY_EPOCH_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit post-recovery continuity epoch evidence must cover every required control"
            )
        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit post-recovery continuity epoch evidence must be canonicalized"
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
    def previous_epoch_reference(self) -> str:
        return self.recovery_acceptance.epoch_reference

    @property
    def reattestation_reference(self) -> str:
        return self.recovery_acceptance.reattestation_reference

    @property
    def operational_status(self) -> NIIRunAuditPhysicalAdapterProductionOperationalStatus:
        return self.recovery_acceptance.operational_status

    @property
    def intervention_acceptance_reference(self) -> str:
        return self.recovery_acceptance.intervention_acceptance_reference

    @property
    def intervention_authorization_reference(self) -> str:
        return self.recovery_acceptance.intervention_authorization_reference

    @property
    def intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.recovery_acceptance.intervention_action

    @property
    def previous_recovery_authorization_reference(self) -> str:
        return self.recovery_acceptance.previous_recovery_authorization_reference

    @property
    def previous_operations_reference(self) -> str:
        return self.recovery_acceptance.previous_operations_reference

    @property
    def adapter_reference(self) -> str:
        return self.recovery_acceptance.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.recovery_acceptance.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.recovery_acceptance.artifact_reference
