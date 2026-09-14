from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER,
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINTS,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError(
    ValueError
):
    """Raised when a post-recovery intervention receipt cannot be recorded safely."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt:
    """Immutable receipt for externally observed post-recovery intervention results."""

    intervention_authorization: (
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization
    )
    receipt_reference: str
    intervention_reference: str
    status: NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus
    checkpoint_results: tuple[
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult, ...
    ]

    def __post_init__(self) -> None:
        required_references = {
            "receipt_reference": self.receipt_reference,
            "intervention_reference": self.intervention_reference,
        }
        for name, value in required_references.items():
            if not value.strip():
                raise ValueError(
                    f"NII audit post-recovery operational intervention {name} is required"
                )

        if not self.intervention_authorization.authorization_reference.strip():
            raise ValueError(
                "NII audit post-recovery operational intervention requires a valid authorization"
            )
        if not self.intervention_authorization.reattestation_reference.strip():
            raise ValueError(
                "NII audit post-recovery operational intervention requires a valid status re-attestation"
            )
        if (
            self.intervention_authorization.status
            is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
        ):
            raise ValueError(
                "HEALTHY NII audit post-recovery operational status cannot have an intervention receipt"
            )
        if (
            self.intervention_authorization.authorization_reference
            == self.intervention_authorization.previous_intervention_authorization_reference
        ):
            raise ValueError(
                "NII audit post-recovery intervention receipt requires a distinct authorization cycle"
            )

        checkpoints = tuple(item.checkpoint for item in self.checkpoint_results)
        if len(checkpoints) != len(set(checkpoints)):
            raise ValueError(
                "Duplicate NII audit post-recovery operational intervention checkpoint result"
            )
        if (
            frozenset(checkpoints)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINTS
        ):
            raise ValueError(
                "NII audit post-recovery operational intervention checkpoint results must cover "
                "every required checkpoint"
            )
        if (
            checkpoints
            != NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
        ):
            raise ValueError(
                "NII audit post-recovery operational intervention checkpoint results must be "
                "canonicalized"
            )

        derived_status = (
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
            if all(
                result.status
                is NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
                for result in self.checkpoint_results
            )
            else NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.FAILED
        )
        if self.status is not derived_status:
            raise ValueError(
                "NII audit post-recovery operational intervention status must match checkpoint results"
            )

    @property
    def authorization_reference(self) -> str:
        return self.intervention_authorization.authorization_reference

    @property
    def action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.intervention_authorization.action

    @property
    def reattestation_reference(self) -> str:
        return self.intervention_authorization.reattestation_reference

    @property
    def operational_status(self) -> NIIRunAuditPhysicalAdapterProductionOperationalStatus:
        return self.intervention_authorization.status

    @property
    def epoch_reference(self) -> str:
        return self.intervention_authorization.epoch_reference

    @property
    def previous_operations_reference(self) -> str:
        return self.intervention_authorization.previous_operations_reference

    @property
    def previous_attestation_reference(self) -> str:
        return self.intervention_authorization.previous_attestation_reference

    @property
    def recovery_acceptance_reference(self) -> str:
        return self.intervention_authorization.recovery_acceptance_reference

    @property
    def recovery_receipt_reference(self) -> str:
        return self.intervention_authorization.recovery_receipt_reference

    @property
    def recovery_reference(self) -> str:
        return self.intervention_authorization.recovery_reference

    @property
    def recovery_authorization_reference(self) -> str:
        return self.intervention_authorization.recovery_authorization_reference

    @property
    def recovery_action(self) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction:
        return self.intervention_authorization.recovery_action

    @property
    def previous_intervention_authorization_reference(self) -> str:
        return self.intervention_authorization.previous_intervention_authorization_reference

    @property
    def previous_intervention_action(
        self,
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction:
        return self.intervention_authorization.previous_intervention_action

    @property
    def adapter_reference(self) -> str:
        return self.intervention_authorization.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.intervention_authorization.environment_reference

    @property
    def artifact_reference(self) -> str:
        return self.intervention_authorization.artifact_reference
