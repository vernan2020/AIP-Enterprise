from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NIIAuditPersistenceRequirement(str, Enum):
    """Capabilities that a physical NII audit repository must certify."""

    ATOMIC_PUT_IF_ABSENT = "ATOMIC_PUT_IF_ABSENT"
    UNIQUE_RUN_REFERENCE = "UNIQUE_RUN_REFERENCE"
    IMMUTABLE_RECORDS = "IMMUTABLE_RECORDS"
    ROUND_TRIP_SERIALIZATION = "ROUND_TRIP_SERIALIZATION"
    SCHEMA_VERSIONING = "SCHEMA_VERSIONING"
    MIGRATION_SAFETY = "MIGRATION_SAFETY"
    TRANSACTIONAL_DURABILITY = "TRANSACTIONAL_DURABILITY"
    READ_AFTER_WRITE_CONSISTENCY = "READ_AFTER_WRITE_CONSISTENCY"
    INTEGRITY_VERIFICATION = "INTEGRITY_VERIFICATION"
    RECOVERY_VERIFICATION = "RECOVERY_VERIFICATION"


REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS = frozenset(NIIAuditPersistenceRequirement)


class NIIAuditPersistenceReadinessStatus(str, Enum):
    """Certification state for a physical NII audit persistence adapter."""

    READY = "READY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class NIIAuditPersistenceEvidence:
    """Traceable certification evidence for one persistence capability."""

    requirement: NIIAuditPersistenceRequirement
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError("NII audit persistence evidence source_reference is required")


@dataclass(frozen=True, slots=True)
class NIIAuditPersistenceReadinessAssessment:
    """Fail-closed readiness assessment for one physical repository implementation."""

    adapter_reference: str
    status: NIIAuditPersistenceReadinessStatus
    certified_requirements: frozenset[NIIAuditPersistenceRequirement]
    missing_requirements: frozenset[NIIAuditPersistenceRequirement]
    evidence: tuple[NIIAuditPersistenceEvidence, ...]

    def __post_init__(self) -> None:
        if not self.adapter_reference.strip():
            raise ValueError("NII audit persistence adapter_reference is required")
        if self.certified_requirements & self.missing_requirements:
            raise ValueError(
                "NII audit persistence requirements cannot be both certified and missing"
            )
        if (
            self.certified_requirements | self.missing_requirements
            != REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS
        ):
            raise ValueError(
                "NII audit persistence assessment must cover every required capability"
            )
        if self.status is NIIAuditPersistenceReadinessStatus.READY and self.missing_requirements:
            raise ValueError(
                "READY NII audit persistence assessment cannot have missing requirements"
            )
        if (
            self.status is NIIAuditPersistenceReadinessStatus.BLOCKED
            and not self.missing_requirements
        ):
            raise ValueError(
                "BLOCKED NII audit persistence assessment requires missing requirements"
            )

    @property
    def is_ready(self) -> bool:
        return self.status is NIIAuditPersistenceReadinessStatus.READY
