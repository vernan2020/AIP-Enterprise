from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_acceptance import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_ACCEPTANCE_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence,
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
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError(
    ValueError
):
    """Raised when post-recovery operational recovery acceptance cannot be issued safely."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance:
    """Positive-only acceptance of one exact successful post-recovery recovery receipt."""

    recovery_receipt: NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt
    acceptance_reference: str
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence, ...]

    def __post_init__(self) -> None:
        if (
            self.recovery_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
        ):
            raise ValueError(
                "NII audit post-recovery operational recovery acceptance requires a successful receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
            for result in self.recovery_receipt.checkpoint_results
        ):
            raise ValueError(
                "NII audit post-recovery operational recovery acceptance requires every checkpoint to succeed"
            )
        if (
            self.recovery_receipt.authorization_reference
            == self.recovery_receipt.previous_recovery_authorization_reference
        ):
            raise ValueError(
                "NII audit post-recovery operational recovery acceptance requires a distinct recovery cycle"
            )
        if not self.acceptance_reference.strip():
            raise ValueError(
                "NII audit post-recovery operational recovery acceptance_reference is required"
            )

        requirements = tuple(item.requirement for item in self.evidence)
        if len(requirements) != len(set(requirements)):
            raise ValueError(
                "Duplicate NII audit post-recovery operational recovery acceptance evidence requirement"
            )
        if (
            frozenset(requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_ACCEPTANCE_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit post-recovery operational recovery acceptance evidence must cover every required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit post-recovery operational recovery acceptance evidence must be canonicalized"
            )

    @property
    def recovery_receipt_reference(self) -> str:
        return self.recovery_receipt.receipt_reference

    @property
    def recovery_reference(self) -> str:
        return self.recovery_receipt.recovery_reference

    @property
    def recovery_authorization_reference(self) -> str:
        return self.recovery_receipt.authorization_reference

    @property
    def recovery_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.recovery_receipt.action

    @property
    def intervention_acceptance_reference(self) -> str:
        return self.recovery_receipt.intervention_acceptance_reference

    @property
    def intervention_receipt_reference(self) -> str:
        return self.recovery_receipt.intervention_receipt_reference

    @property
    def intervention_reference(self) -> str:
        return self.recovery_receipt.intervention_reference

    @property
    def intervention_authorization_reference(self) -> str:
        return self.recovery_receipt.intervention_authorization_reference

    @property
    def intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.recovery_receipt.intervention_action

    @property
    def reattestation_reference(self) -> str:
        return self.recovery_receipt.reattestation_reference

    @property
    def operational_status(self) -> NIIRunAuditPhysicalAdapterProductionOperationalStatus:
        return self.recovery_receipt.operational_status

    @property
    def epoch_reference(self) -> str:
        return self.recovery_receipt.epoch_reference

    @property
    def previous_operations_reference(self) -> str:
        return self.recovery_receipt.previous_operations_reference

    @property
    def previous_attestation_reference(self) -> str:
        return self.recovery_receipt.previous_attestation_reference

    @property
    def previous_recovery_acceptance_reference(self) -> str:
        return self.recovery_receipt.previous_recovery_acceptance_reference

    @property
    def previous_recovery_receipt_reference(self) -> str:
        return self.recovery_receipt.previous_recovery_receipt_reference

    @property
    def previous_recovery_reference(self) -> str:
        return self.recovery_receipt.previous_recovery_reference

    @property
    def previous_recovery_authorization_reference(self) -> str:
        return self.recovery_receipt.previous_recovery_authorization_reference

    @property
    def previous_recovery_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.recovery_receipt.previous_recovery_action

    @property
    def previous_intervention_authorization_reference(self) -> str:
        return self.recovery_receipt.previous_intervention_authorization_reference

    @property
    def previous_intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.recovery_receipt.previous_intervention_action

    @property
    def adapter_reference(self) -> str:
        return self.recovery_receipt.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.recovery_receipt.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.recovery_receipt.artifact_reference
