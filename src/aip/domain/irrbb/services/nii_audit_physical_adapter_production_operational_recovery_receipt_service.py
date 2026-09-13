from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER,
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINTS,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService:
    """Record externally observed outcomes for one authorized return-to-service action."""

    @classmethod
    def record(
        cls,
        *,
        recovery_authorization: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization,
        receipt_reference: str,
        recovery_reference: str,
        checkpoint_results: Iterable[
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt:
        if not receipt_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError(
                "NII audit operational recovery receipt_reference is required"
            )
        if not recovery_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError(
                "NII audit operational recovery recovery_reference is required"
            )

        result_items = tuple(checkpoint_results)
        results_by_checkpoint = {}
        for item in result_items:
            if item.checkpoint in results_by_checkpoint:
                raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError(
                    "Duplicate NII audit operational recovery checkpoint result"
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
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError(
                "NII audit operational recovery checkpoint results must cover every required checkpoint"
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
        return NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt(
            recovery_authorization=recovery_authorization,
            receipt_reference=receipt_reference,
            recovery_reference=recovery_reference,
            status=status,
            checkpoint_results=canonical_results,
        )
