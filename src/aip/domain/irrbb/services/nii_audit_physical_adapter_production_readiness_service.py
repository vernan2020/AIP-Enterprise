from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_certification import (
    NIIRunAuditPhysicalAdapterCertificationBundle,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_readiness import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionEvidence,
    NIIRunAuditPhysicalAdapterProductionReadinessAssessment,
    NIIRunAuditPhysicalAdapterProductionReadinessError,
    NIIRunAuditPhysicalAdapterProductionReadinessStatus,
    NIIRunAuditPhysicalAdapterProductionRequirement,
)


class NIIRunAuditPhysicalAdapterProductionReadinessService:
    """Assess source-neutral production readiness for one certified physical adapter."""

    @classmethod
    def assess(
        cls,
        *,
        certification_bundle: NIIRunAuditPhysicalAdapterCertificationBundle,
        environment_reference: str,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionEvidence],
    ) -> NIIRunAuditPhysicalAdapterProductionReadinessAssessment:
        if not environment_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionReadinessError(
                "NII audit physical adapter production environment_reference is required"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement: dict[
            NIIRunAuditPhysicalAdapterProductionRequirement,
            NIIRunAuditPhysicalAdapterProductionEvidence,
        ] = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionReadinessError(
                    "Duplicate NII audit physical adapter production evidence for "
                    f"{item.requirement.value}"
                )
            evidence_by_requirement[item.requirement] = item

        certified = frozenset(evidence_by_requirement)
        missing = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_REQUIREMENTS - certified
        )
        status = (
            NIIRunAuditPhysicalAdapterProductionReadinessStatus.READY
            if not missing
            else NIIRunAuditPhysicalAdapterProductionReadinessStatus.BLOCKED
        )
        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )

        return NIIRunAuditPhysicalAdapterProductionReadinessAssessment(
            certification_bundle=certification_bundle,
            environment_reference=environment_reference,
            status=status,
            certified_requirements=certified,
            missing_requirements=missing,
            evidence=canonical_evidence,
        )
