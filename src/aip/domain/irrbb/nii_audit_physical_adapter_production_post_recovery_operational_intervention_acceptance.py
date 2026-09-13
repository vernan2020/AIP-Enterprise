from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError(
    ValueError
):
    """Raised when post-recovery intervention acceptance cannot be issued safely."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance:
    """Positive-only acceptance of one exact successful Phase 59 receipt."""

    intervention_receipt: (
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt
    )
    acceptance_reference: str
    evidence: tuple[
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence, ...
    ]

    def __post_init__(self) -> None:
        if (
            self.intervention_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
        ):
            raise ValueError(
                "NII audit post-recovery intervention acceptance requires a successful receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
            for result in self.intervention_receipt.checkpoint_results
        ):
            raise ValueError(
                "NII audit post-recovery intervention acceptance requires every checkpoint to succeed"
            )
        if (
            self.intervention_receipt.authorization_reference
            == self.intervention_receipt.previous_intervention_authorization_reference
        ):
            raise ValueError(
                "NII audit post-recovery intervention acceptance requires a distinct authorization cycle"
            )
        if not self.acceptance_reference.strip():
            raise ValueError(
                "NII audit post-recovery intervention acceptance_reference is required"
            )

        requirements = tuple(item.requirement for item in self.evidence)
        if len(requirements) != len(set(requirements)):
            raise ValueError(
                "Duplicate NII audit post-recovery intervention acceptance evidence requirement"
            )
        if (
            frozenset(requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit post-recovery intervention acceptance evidence must cover every "
                "required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit post-recovery intervention acceptance evidence must be canonicalized"
            )

    @property
    def intervention_receipt_reference(self) -> str:
        return self.intervention_receipt.receipt_reference

    @property
    def intervention_reference(self) -> str:
        return self.intervention_receipt.intervention_reference

    @property
    def authorization_reference(self) -> str:
        return self.intervention_receipt.authorization_reference

    @property
    def action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.intervention_receipt.action

    @property
    def reattestation_reference(self) -> str:
        return self.intervention_receipt.reattestation_reference

    @property
    def operational_status(self) -> NIIRunAuditPhysicalAdapterProductionOperationalStatus:
        return self.intervention_receipt.operational_status

    @property
    def epoch_reference(self) -> str:
        return self.intervention_receipt.epoch_reference

    @property
    def previous_operations_reference(self) -> str:
        return self.intervention_receipt.previous_operations_reference

    @property
    def previous_attestation_reference(self) -> str:
        return self.intervention_receipt.previous_attestation_reference

    @property
    def recovery_acceptance_reference(self) -> str:
        return self.intervention_receipt.recovery_acceptance_reference

    @property
    def recovery_receipt_reference(self) -> str:
        return self.intervention_receipt.recovery_receipt_reference

    @property
    def recovery_reference(self) -> str:
        return self.intervention_receipt.recovery_reference

    @property
    def recovery_authorization_reference(self) -> str:
        return self.intervention_receipt.recovery_authorization_reference

    @property
    def recovery_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.intervention_receipt.recovery_action

    @property
    def previous_intervention_authorization_reference(self) -> str:
        return self.intervention_receipt.previous_intervention_authorization_reference

    @property
    def previous_intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.intervention_receipt.previous_intervention_action

    @property
    def adapter_reference(self) -> str:
        return self.intervention_receipt.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.intervention_receipt.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.intervention_receipt.artifact_reference
