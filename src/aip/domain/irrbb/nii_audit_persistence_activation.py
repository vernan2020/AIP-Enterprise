from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.nii_audit_persistence_readiness import (
    NIIAuditPersistenceReadinessAssessment,
)
from aip.domain.irrbb.nii_audit_schema_evolution import NIIAuditSchemaEvolutionContract
from aip.domain.irrbb.nii_audit_serialization_compatibility import (
    NIIRunAuditSerializationCompatibilityCertificate,
)


class NIIRunAuditPersistenceActivationError(ValueError):
    """Raised when a physical NII audit persistence configuration is not authorized."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPersistenceActivationConfiguration:
    """Explicit technical identities intended for one physical persistence activation."""

    adapter_reference: str
    schema_contract: NIIAuditSchemaEvolutionContract
    codec_reference: str
    integrity_reference: str
    source_reference: str

    def __post_init__(self) -> None:
        if not self.adapter_reference.strip():
            raise ValueError("NII audit activation adapter_reference is required")
        if not self.codec_reference.strip():
            raise ValueError("NII audit activation codec_reference is required")
        if not self.integrity_reference.strip():
            raise ValueError("NII audit activation integrity_reference is required")
        if not self.source_reference.strip():
            raise ValueError("NII audit activation source_reference is required")


@dataclass(frozen=True, slots=True)
class NIIRunAuditPersistenceActivationAuthorization:
    """Positive-only proof that one exact persistence configuration may be activated."""

    configuration: NIIRunAuditPersistenceActivationConfiguration
    readiness: NIIAuditPersistenceReadinessAssessment
    compatibility: NIIRunAuditSerializationCompatibilityCertificate

    def __post_init__(self) -> None:
        if not self.readiness.is_ready:
            raise ValueError("NII audit persistence activation requires READY assessment")
        if self.readiness.adapter_reference != self.configuration.adapter_reference:
            raise ValueError("NII audit persistence activation adapter identity mismatch")
        if self.compatibility.schema_contract != self.configuration.schema_contract:
            raise ValueError("NII audit persistence activation schema contract mismatch")
        if self.compatibility.codec_reference != self.configuration.codec_reference:
            raise ValueError("NII audit persistence activation codec identity mismatch")
        if self.compatibility.integrity_reference != self.configuration.integrity_reference:
            raise ValueError("NII audit persistence activation integrity identity mismatch")
