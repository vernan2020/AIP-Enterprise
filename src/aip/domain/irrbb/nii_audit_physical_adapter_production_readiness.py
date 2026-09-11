from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_audit_physical_adapter_certification import (
    NIIRunAuditPhysicalAdapterCertificationBundle,
)


class NIIRunAuditPhysicalAdapterProductionReadinessError(ValueError):
    """Raised when physical adapter production readiness cannot be assessed."""


class NIIRunAuditPhysicalAdapterProductionRequirement(str, Enum):
    """Source-neutral evidence requirements before production promotion can be considered."""

    TARGET_ENVIRONMENT_IDENTIFIED = "TARGET_ENVIRONMENT_IDENTIFIED"
    CONNECTIVITY_VALIDATED = "CONNECTIVITY_VALIDATED"
    ACCESS_CONTROL_VALIDATED = "ACCESS_CONTROL_VALIDATED"
    SECRET_HANDLING_VALIDATED = "SECRET_HANDLING_VALIDATED"
    ENCRYPTION_VALIDATED = "ENCRYPTION_VALIDATED"
    SCHEMA_CHANGE_PATH_VALIDATED = "SCHEMA_CHANGE_PATH_VALIDATED"
    BACKUP_RESTORE_PATH_VALIDATED = "BACKUP_RESTORE_PATH_VALIDATED"
    OBSERVABILITY_VALIDATED = "OBSERVABILITY_VALIDATED"
    CAPACITY_VALIDATED = "CAPACITY_VALIDATED"
    ROLLBACK_PATH_VALIDATED = "ROLLBACK_PATH_VALIDATED"


REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_REQUIREMENTS = frozenset(
    NIIRunAuditPhysicalAdapterProductionRequirement
)


class NIIRunAuditPhysicalAdapterProductionReadinessStatus(str, Enum):
    """Readiness state for one certified adapter in one target environment."""

    READY = "READY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionEvidence:
    """Traceable evidence for one production-readiness requirement."""

    requirement: NIIRunAuditPhysicalAdapterProductionRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError(
                "NII audit physical adapter production evidence source_reference is required"
            )


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterProductionReadinessAssessment:
    """Fail-closed production-readiness assessment for one certified adapter candidate."""

    certification_bundle: NIIRunAuditPhysicalAdapterCertificationBundle
    environment_reference: str
    status: NIIRunAuditPhysicalAdapterProductionReadinessStatus
    certified_requirements: frozenset[
        NIIRunAuditPhysicalAdapterProductionRequirement
    ]
    missing_requirements: frozenset[NIIRunAuditPhysicalAdapterProductionRequirement]
    evidence: tuple[NIIRunAuditPhysicalAdapterProductionEvidence, ...]

    def __post_init__(self) -> None:
        if not self.environment_reference.strip():
            raise ValueError(
                "NII audit physical adapter production environment_reference is required"
            )
        if self.certified_requirements & self.missing_requirements:
            raise ValueError(
                "NII audit physical adapter production requirements cannot be both certified and missing"
            )
        if (
            self.certified_requirements | self.missing_requirements
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit physical adapter production assessment must cover every required capability"
            )

        evidence_requirements = tuple(item.requirement for item in self.evidence)
        if len(evidence_requirements) != len(set(evidence_requirements)):
            raise ValueError(
                "Duplicate NII audit physical adapter production evidence requirement"
            )
        if frozenset(evidence_requirements) != self.certified_requirements:
            raise ValueError(
                "NII audit physical adapter production evidence must match certified requirements"
            )
        canonical_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        if self.evidence != canonical_evidence:
            raise ValueError(
                "NII audit physical adapter production evidence must be canonicalized"
            )

        if (
            self.status
            is NIIRunAuditPhysicalAdapterProductionReadinessStatus.READY
            and self.missing_requirements
        ):
            raise ValueError(
                "READY NII audit physical adapter production assessment cannot have missing requirements"
            )
        if (
            self.status
            is NIIRunAuditPhysicalAdapterProductionReadinessStatus.BLOCKED
            and not self.missing_requirements
        ):
            raise ValueError(
                "BLOCKED NII audit physical adapter production assessment requires missing requirements"
            )

    @property
    def is_ready(self) -> bool:
        return self.status is NIIRunAuditPhysicalAdapterProductionReadinessStatus.READY

    @property
    def adapter_reference(self) -> str:
        return self.certification_bundle.descriptor.adapter_reference
