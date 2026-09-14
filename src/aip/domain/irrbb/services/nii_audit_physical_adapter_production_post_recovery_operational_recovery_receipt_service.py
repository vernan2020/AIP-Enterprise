from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER,
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINTS,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptService:
    """Record externally observed outcomes for one authorized post-recovery recovery."""

    @classmethod
    def record(
        cls,
        *,
        recovery_authorization: (
            NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization
        ),
        receipt_reference: str,
        recovery_reference: str,
        checkpoint_results: Iterable[
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt:
        if not receipt_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError(
                "NII audit post-recovery operational recovery receipt_reference is required"
            )
        if not recovery_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError(
                "NII audit post-recovery operational recovery recovery_reference is required"
            )
        if not recovery_authorization.authorization_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError(
                "NII audit post-recovery operational recovery requires a valid authorization"
            )
        if (
            recovery_authorization.authorization_reference
            == recovery_authorization.previous_recovery_authorization_reference
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError(
                "NII audit post-recovery recovery receipt requires a distinct authorization cycle"
            )

        result_items = tuple(checkpoint_results)
        results_by_checkpoint = {}
        for item in result_items:
            if item.checkpoint in results_by_checkpoint:
                raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError(
                    "Duplicate NII audit post-recovery operational recovery checkpoint result"
                )
            results_by_checkpoint[item.checkpoint] = item

        missing_checkpoints = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINTS
            - set(results_by_checkpoint)
        )
        unexpected_checkpoints = set(results_by_checkpoint) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINTS
        )
        if missing_checkpoints or unexpected_checkpoints:
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError(
                "NII audit post-recovery operational recovery checkpoint results must cover "
                "every required checkpoint"
            )

        canonical_results = tuple(
            results_by_checkpoint[checkpoint]
            for checkpoint in NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
        )
        status = (
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
            if all(
                result.status
                is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
                for result in canonical_results
            )
            else NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.FAILED
        )
        return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt(
            recovery_authorization=recovery_authorization,
            receipt_reference=receipt_reference,
            recovery_reference=recovery_reference,
            status=status,
            checkpoint_results=canonical_results,
        )
