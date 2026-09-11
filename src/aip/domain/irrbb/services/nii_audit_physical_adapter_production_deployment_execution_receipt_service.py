from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_execution_authorization import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_execution_receipt import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceipt,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus,
    NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus,
    NIIRunAuditPhysicalAdapterProductionDeploymentStepResult,
    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus,
)


class NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService:
    """Record an immutable receipt for results reported by an external executor."""

    @classmethod
    def record(
        cls,
        *,
        execution_authorization: NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization,
        receipt_reference: str,
        execution_reference: str,
        step_results: Iterable[NIIRunAuditPhysicalAdapterProductionDeploymentStepResult],
        rollback_status: NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus,
        rollback_evidence_reference: str,
    ) -> NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceipt:
        required_references = {
            "receipt_reference": receipt_reference,
            "execution_reference": execution_reference,
            "rollback_evidence_reference": rollback_evidence_reference,
        }
        for name, value in required_references.items():
            if not value.strip():
                raise NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError(
                    f"NII audit physical adapter production deployment execution {name} is required"
                )

        result_items = tuple(step_results)
        result_by_sequence: dict[
            int, NIIRunAuditPhysicalAdapterProductionDeploymentStepResult
        ] = {}
        for result in result_items:
            if result.sequence in result_by_sequence:
                raise NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError(
                    "Duplicate NII audit physical adapter production deployment execution step result for "
                    f"sequence {result.sequence}"
                )
            result_by_sequence[result.sequence] = result

        expected_sequences = tuple(
            step.sequence for step in execution_authorization.deployment_plan.steps
        )
        missing_sequences = set(expected_sequences) - set(result_by_sequence)
        unexpected_sequences = set(result_by_sequence) - set(expected_sequences)
        if missing_sequences or unexpected_sequences:
            details: list[str] = []
            if missing_sequences:
                details.append(
                    "missing="
                    + ",".join(str(sequence) for sequence in sorted(missing_sequences))
                )
            if unexpected_sequences:
                details.append(
                    "unexpected="
                    + ",".join(str(sequence) for sequence in sorted(unexpected_sequences))
                )
            raise NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError(
                "NII audit physical adapter production deployment execution step results do not match authorized plan: "
                + "; ".join(details)
            )

        canonical_results = tuple(
            result_by_sequence[sequence] for sequence in expected_sequences
        )
        status = (
            NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.SUCCEEDED
            if all(
                result.status
                is NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED
                for result in canonical_results
            )
            else NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.FAILED
        )

        if (
            status
            is NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.SUCCEEDED
            and rollback_status
            is not NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED
        ):
            raise NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError(
                "Successful NII audit physical adapter production deployment execution cannot require rollback"
            )

        return NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceipt(
            execution_authorization=execution_authorization,
            receipt_reference=receipt_reference,
            execution_reference=execution_reference,
            status=status,
            step_results=canonical_results,
            rollback_status=rollback_status,
            rollback_evidence_reference=rollback_evidence_reference,
        )
