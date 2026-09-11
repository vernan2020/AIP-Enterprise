from __future__ import annotations

from aip.domain.irrbb.nii_audit_persistence_readiness import (
    REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
    NIIAuditPersistenceEvidence,
    NIIAuditPersistenceReadinessAssessment,
    NIIAuditPersistenceReadinessStatus,
    NIIAuditPersistenceRequirement,
)


class NIIAuditPersistenceReadinessService:
    """Assess physical audit persistence capabilities from explicit certification evidence."""

    @classmethod
    def assess(
        cls,
        *,
        adapter_reference: str,
        evidence: tuple[NIIAuditPersistenceEvidence, ...],
    ) -> NIIAuditPersistenceReadinessAssessment:
        if not adapter_reference.strip():
            raise ValueError("NII audit persistence adapter_reference is required")

        evidence_by_requirement: dict[
            NIIAuditPersistenceRequirement,
            NIIAuditPersistenceEvidence,
        ] = {}
        for item in evidence:
            if item.requirement in evidence_by_requirement:
                raise ValueError(
                    f"Duplicate NII audit persistence evidence for {item.requirement.value}"
                )
            evidence_by_requirement[item.requirement] = item

        certified = frozenset(evidence_by_requirement)
        missing = REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS - certified
        status = (
            NIIAuditPersistenceReadinessStatus.READY
            if not missing
            else NIIAuditPersistenceReadinessStatus.BLOCKED
        )
        return NIIAuditPersistenceReadinessAssessment(
            adapter_reference=adapter_reference,
            status=status,
            certified_requirements=certified,
            missing_requirements=missing,
            evidence=evidence,
        )
