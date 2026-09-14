from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_authorization import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER,
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINTS,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus,
)


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService:
    """Record externally observed outcomes for one authorized runtime activation."""

    @classmethod
    def record(
        cls,
        *,
        activation_authorization: NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization,
        receipt_reference: str,
        activation_reference: str,
        checkpoint_results: Iterable[
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointResult
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt:
        if not receipt_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError(
                "NII audit physical adapter production runtime activation receipt_reference "
                "is required"
            )
        if not activation_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError(
                "NII audit physical adapter production runtime activation activation_reference "
                "is required"
            )

        result_items = tuple(checkpoint_results)
        results_by_checkpoint = {}
        for item in result_items:
            if item.checkpoint in results_by_checkpoint:
                raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError(
                    "Duplicate NII audit physical adapter production runtime activation "
                    "checkpoint result"
                )
            results_by_checkpoint[item.checkpoint] = item

        missing_checkpoints = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINTS
            - set(results_by_checkpoint)
        )
        unexpected_checkpoints = set(results_by_checkpoint) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINTS
        )
        if missing_checkpoints or unexpected_checkpoints:
            raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError(
                "NII audit physical adapter production runtime activation checkpoint results "
                "must cover every required checkpoint"
            )

        canonical_results = tuple(
            results_by_checkpoint[checkpoint]
            for checkpoint in NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER
        )
        status = (
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.SUCCEEDED
            if all(
                result.status
                is NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.SUCCEEDED
                for result in canonical_results
            )
            else NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.FAILED
        )
        return NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt(
            activation_authorization=activation_authorization,
            receipt_reference=receipt_reference,
            activation_reference=activation_reference,
            status=status,
            checkpoint_results=canonical_results,
        )
