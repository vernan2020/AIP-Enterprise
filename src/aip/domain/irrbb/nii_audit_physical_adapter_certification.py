from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.nii_audit_persistence_activation import (
    NIIRunAuditPersistenceActivationAuthorization,
)
from aip.domain.irrbb.nii_audit_persistence_readiness import (
    NIIAuditPersistenceReadinessAssessment,
)
from aip.domain.irrbb.nii_audit_physical_persistence import (
    NIIRunAuditActivatedPhysicalPersistence,
    NIIRunAuditPhysicalPersistenceDescriptor,
)
from aip.domain.irrbb.nii_audit_serialization_compatibility import (
    NIIRunAuditSerializationCompatibilityCertificate,
)
from aip.domain.irrbb.nii_run_audit_ports import NIIRunAuditRepository


class NIIRunAuditPhysicalAdapterCertificationError(ValueError):
    """Raised when a physical NII audit adapter cannot be certified."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalAdapterCertificationBundle:
    """Positive-only auditable evidence bundle for one activated physical adapter."""

    certification_reference: str
    activated_persistence: NIIRunAuditActivatedPhysicalPersistence
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.certification_reference.strip():
            raise ValueError("NII audit physical adapter certification_reference is required")
        if not self.evidence_references:
            raise ValueError("NII audit physical adapter certification evidence is required")
        if any(not reference.strip() for reference in self.evidence_references):
            raise ValueError("NII audit physical adapter certification evidence reference is required")
        if self.evidence_references != tuple(sorted(self.evidence_references)):
            raise ValueError("NII audit physical adapter certification evidence must be canonicalized")
        if len(self.evidence_references) != len(set(self.evidence_references)):
            raise ValueError("Duplicate NII audit physical adapter certification evidence reference")

        authorization = self.activated_persistence.authorization
        descriptor = self.activated_persistence.descriptor
        configuration = authorization.configuration
        if not authorization.readiness.is_ready:
            raise ValueError("NII audit physical adapter certification requires READY assessment")
        if authorization.readiness.adapter_reference != descriptor.adapter_reference:
            raise ValueError("NII audit physical adapter certification readiness identity mismatch")
        if configuration.adapter_reference != descriptor.adapter_reference:
            raise ValueError("NII audit physical adapter certification adapter identity mismatch")
        if authorization.compatibility.schema_contract != descriptor.schema_contract:
            raise ValueError("NII audit physical adapter certification schema contract mismatch")
        if authorization.compatibility.codec_reference != descriptor.codec_reference:
            raise ValueError("NII audit physical adapter certification codec identity mismatch")
        if authorization.compatibility.integrity_reference != descriptor.integrity_reference:
            raise ValueError("NII audit physical adapter certification integrity identity mismatch")

    @property
    def authorization(self) -> NIIRunAuditPersistenceActivationAuthorization:
        return self.activated_persistence.authorization

    @property
    def readiness(self) -> NIIAuditPersistenceReadinessAssessment:
        return self.authorization.readiness

    @property
    def compatibility(self) -> NIIRunAuditSerializationCompatibilityCertificate:
        return self.authorization.compatibility

    @property
    def descriptor(self) -> NIIRunAuditPhysicalPersistenceDescriptor:
        return self.activated_persistence.descriptor

    @property
    def repository(self) -> NIIRunAuditRepository:
        return self.activated_persistence.repository
