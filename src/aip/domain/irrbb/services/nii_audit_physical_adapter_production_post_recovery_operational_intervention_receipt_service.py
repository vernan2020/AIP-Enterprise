from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER,
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINTS,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService:
    """Record externally observed outcomes for one authorized post-recovery intervention."""

    @classmethod
    def record(
        cls,
        *,
        intervention_authorization: (
            NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization
        ),
        receipt_reference: str,
        intervention_reference: str,
        checkpoint_results: Iterable[
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt:
        if not receipt_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError(
                "NII audit post-recovery operational intervention receipt_reference is required"
            )
        if not intervention_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError(
                "NII audit post-recovery operational intervention intervention_reference is required"
            )
        if not intervention_authorization.authorization_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError(
                "NII audit post-recovery operational intervention requires a valid authorization"
            )
        if not intervention_authorization.reattestation_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError(
                "NII audit post-recovery operational intervention requires a valid status re-attestation"
            )
        if (
            intervention_authorization.status
            is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError(
                "HEALTHY NII audit post-recovery operational status cannot have an intervention receipt"
            )
        if (
            intervention_authorization.authorization_reference
            == intervention_authorization.previous_intervention_authorization_reference
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError(
                "NII audit post-recovery intervention receipt requires a distinct authorization cycle"
            )

        result_items = tuple(checkpoint_results)
        results_by_checkpoint = {}
        for item in result_items:
            if item.checkpoint in results_by_checkpoint:
                raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError(
                    "Duplicate NII audit post-recovery operational intervention checkpoint result"
                )
            results_by_checkpoint[item.checkpoint] = item

        missing_checkpoints = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINTS
            - set(results_by_checkpoint)
        )
        unexpected_checkpoints = set(results_by_checkpoint) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINTS
        )
        if missing_checkpoints or unexpected_checkpoints:
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptError(
                "NII audit post-recovery operational intervention checkpoint results must cover "
                "every required checkpoint"
            )

        canonical_results = tuple(
            results_by_checkpoint[checkpoint]
            for checkpoint in NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
        )
        status = (
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
            if all(
                result.status
                is NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
                for result in canonical_results
            )
            else NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.FAILED
        )
        return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt(
            intervention_authorization=intervention_authorization,
            receipt_reference=receipt_reference,
            intervention_reference=intervention_reference,
            status=status,
            checkpoint_results=canonical_results,
        )
