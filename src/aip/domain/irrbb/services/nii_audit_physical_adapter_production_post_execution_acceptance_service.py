from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_execution_receipt import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceipt,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus,
    NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_execution_acceptance import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_POST_EXECUTION_ACCEPTANCE_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance,
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError,
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceEvidence,
)


class NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceService:
    """Issue positive-only acceptance for one exact successful execution receipt."""

    @classmethod
    def accept(
        cls,
        *,
        execution_receipt: NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceipt,
        acceptance_reference: str,
        evidence: Iterable[
            NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceEvidence
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance:
        if (
            execution_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.SUCCEEDED
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError(
                "NII audit physical adapter production post-execution acceptance requires "
                "a successful execution receipt"
            )
        if (
            execution_receipt.rollback_status
            is not NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError(
                "NII audit physical adapter production post-execution acceptance requires "
                "rollback status NOT_REQUIRED"
            )
        if not acceptance_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError(
                "NII audit physical adapter production post-execution acceptance_reference "
                "is required"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError(
                    "Duplicate NII audit physical adapter production post-execution "
                    "acceptance evidence requirement"
                )
            evidence_by_requirement[item.requirement] = item

        missing_requirements = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_POST_EXECUTION_ACCEPTANCE_REQUIREMENTS
            - set(evidence_by_requirement)
        )
        unexpected_requirements = set(evidence_by_requirement) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_POST_EXECUTION_ACCEPTANCE_REQUIREMENTS
        )
        if missing_requirements or unexpected_requirements:
            raise NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError(
                "NII audit physical adapter production post-execution acceptance evidence "
                "must cover every required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance(
            execution_receipt=execution_receipt,
            acceptance_reference=acceptance_reference,
            evidence=canonical_evidence,
        )
