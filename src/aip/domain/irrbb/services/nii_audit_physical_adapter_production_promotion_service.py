from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_promotion import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_PROMOTION_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionPromotionAuthorization,
    NIIRunAuditPhysicalAdapterProductionPromotionError,
    NIIRunAuditPhysicalAdapterProductionPromotionEvidence,
    NIIRunAuditPhysicalAdapterProductionPromotionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_readiness import (
    NIIRunAuditPhysicalAdapterProductionReadinessAssessment,
)


class NIIRunAuditPhysicalAdapterProductionPromotionService:
    """Issue a positive-only production promotion authorization when every gate passes."""

    @classmethod
    def authorize(
        cls,
        *,
        readiness_assessment: NIIRunAuditPhysicalAdapterProductionReadinessAssessment,
        authorization_reference: str,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionPromotionEvidence],
    ) -> NIIRunAuditPhysicalAdapterProductionPromotionAuthorization:
        if not readiness_assessment.is_ready:
            raise NIIRunAuditPhysicalAdapterProductionPromotionError(
                "NII audit physical adapter production promotion requires READY assessment"
            )
        if not authorization_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPromotionError(
                "NII audit physical adapter production promotion authorization_reference is required"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement: dict[
            NIIRunAuditPhysicalAdapterProductionPromotionRequirement,
            NIIRunAuditPhysicalAdapterProductionPromotionEvidence,
        ] = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionPromotionError(
                    "Duplicate NII audit physical adapter production promotion evidence for "
                    f"{item.requirement.value}"
                )
            evidence_by_requirement[item.requirement] = item

        missing = REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_PROMOTION_REQUIREMENTS - frozenset(
            evidence_by_requirement
        )
        if missing:
            missing_references = ", ".join(sorted(item.value for item in missing))
            raise NIIRunAuditPhysicalAdapterProductionPromotionError(
                "NII audit physical adapter production promotion authorization is missing "
                f"required evidence: {missing_references}"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionPromotionAuthorization(
            readiness_assessment=readiness_assessment,
            authorization_reference=authorization_reference,
            evidence=canonical_evidence,
        )
