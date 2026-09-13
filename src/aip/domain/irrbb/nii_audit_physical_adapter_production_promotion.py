from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_production_readiness import (
    NIIRunAuditPhysicalAdapterProductionReadinessAssessment,
)


class NIIRunAuditPhysicalAdapterProductionPromotionError(ValueError):
    """Raised when a production promotion authorization cannot be issued."""


class NIIRunAuditPhysicalAdapterProductionPromotionRequirement(str, Enum):
    """Governance evidence required before one certified adapter may be promoted."""

    CHANGE_AUTHORIZATION_RECORDED = "CHANGE_AUTHORIZATION_RECORDED"
    RISK_OWNER_AUTHORIZATION_RECORDED = "RISK_OWNER_AUTHORIZATION_RECORDED"
    OPERATIONS_OWNER_AUTHORIZATION_RECORDED = "OPERATIONS_OWNER_AUTHORIZATION_RECORDED"
    DEPLOYMENT_WINDOW_AUTHORIZED = "DEPLOYMENT_WINDOW_AUTHORIZED"
    ROLLBACK_AUTHORITY_CONFIRMED = "ROLLBACK_AUTHORITY_CONFIRMED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_PROMOTION_REQUIREMENTS = frozenset(
    NIIRunAuditPhysicalAdapterProductionPromotionRequirement
)


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPromotionEvidence:
    """Traceable evidence for one production-promotion authorization requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionPromotionRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit physical adapter production promotion evidence source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionPromotionAuthorization:
    """Positive-only authorization for one READY adapter candidate and target environment."""

    readiness_assessment: NIIRunAuditPhysicalAdapterProductionReadinessAssessment
    authorization_reference: str
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionPromotionEvidence, ...]

    def __post_init__(self) -> None:
        if not self.readiness_assessment.is_ready:
            raise ValueError(
                "NII audit physical adapter production promotion requires READY assessment"
            )
        if not self.authorization_reference.strip():
            raise ValueError(
                "NII audit physical adapter production promotion authorization_reference is required"
            )

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError(
                "Duplicate NII audit physical adapter production promotion evidence requirement"
            )
        if (
            frozenset(evidence_requirements)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_PROMOTION_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit physical adapter production promotion evidence must cover every required authorization"
            )

        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit physical adapter production promotion evidence must be canonicalized"
            )

    @property
    def adapter_reference(self) -> str:
        return self.readiness_assessment.adapter_reference

    @property
    def environment_reference(self) -> str:
        return self.readiness_assessment.environment_reference
