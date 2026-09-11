from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_execution_authorization import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_DEPLOYMENT_EXECUTION_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationError,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_plan import (
    NIIRunAuditPhysicalAdapterProductionDeploymentPlan,
)


class NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService:
    """Authorize execution of one exact deployment plan when all last-mile gates pass."""

    @classmethod
    def authorize(
        cls,
        *,
        deployment_plan: NIIRunAuditPhysicalAdapterProductionDeploymentPlan,
        execution_authorization_reference: str,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence],
    ) -> NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization:
        if not execution_authorization_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationError(
                "NII audit physical adapter production deployment execution authorization_reference is required"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement: dict[
            NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement,
            NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence,
        ] = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationError(
                    "Duplicate NII audit physical adapter production deployment execution evidence for "
                    f"{item.requirement.value}"
                )
            evidence_by_requirement[item.requirement] = item

        missing = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_DEPLOYMENT_EXECUTION_REQUIREMENTS
            - frozenset(evidence_by_requirement)
        )
        if missing:
            missing_references = ", ".join(sorted(item.value for item in missing))
            raise NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationError(
                "NII audit physical adapter production deployment execution authorization is missing "
                f"required evidence: {missing_references}"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization(
            deployment_plan=deployment_plan,
            execution_authorization_reference=execution_authorization_reference,
            evidence=canonical_evidence,
        )
