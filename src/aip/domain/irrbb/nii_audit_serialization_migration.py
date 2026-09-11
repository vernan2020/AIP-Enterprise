from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aip.domain.irrbb.nii_audit_schema_evolution import NIIAuditSchemaMigrationStep
from aip.domain.irrbb.nii_audit_serialization import NIIRunAuditSerializationEnvelope
from aip.domain.irrbb.nii_run_audit import NIIRunAuditRecord


class NIIRunAuditSerializationMigrationError(ValueError):
    """Raised when explicit NII audit serialization migration invariants fail."""


class NIIRunAuditPayloadMigrationTransformer(Protocol):
    """One explicit payload transformation for one approved schema migration step."""

    @property
    def reference(self) -> str: ...

    @property
    def step(self) -> NIIAuditSchemaMigrationStep: ...

    def migrate(self, *, payload: bytes, run_reference: str) -> bytes: ...


class NIIRunAuditPayloadMigrationTransformerResolver(Protocol):
    """Resolve the explicitly approved transformer for one schema migration step."""

    def resolve(
        self,
        *,
        step: NIIAuditSchemaMigrationStep,
    ) -> NIIRunAuditPayloadMigrationTransformer: ...


@dataclass(frozen=True, slots=True)
class NIIRunAuditAppliedSerializationMigration:
    """Auditable evidence for one applied payload migration step."""

    step: NIIAuditSchemaMigrationStep
    transformer_reference: str
    source_payload_digest: str
    target_payload_digest: str

    def __post_init__(self) -> None:
        if not self.transformer_reference.strip():
            raise ValueError("NII audit migration transformer_reference is required")
        if not self.source_payload_digest.strip():
            raise ValueError("NII audit migration source payload digest is required")
        if not self.target_payload_digest.strip():
            raise ValueError("NII audit migration target payload digest is required")


@dataclass(frozen=True, slots=True)
class NIIRunAuditSerializationMigrationResult:
    """Historical envelope migrated to current schema and decoded as one audit record."""

    source_envelope: NIIRunAuditSerializationEnvelope
    current_envelope: NIIRunAuditSerializationEnvelope
    applied_migrations: tuple[NIIRunAuditAppliedSerializationMigration, ...]
    record: NIIRunAuditRecord

    def __post_init__(self) -> None:
        if self.current_envelope.run_reference != self.source_envelope.run_reference:
            raise ValueError("NII audit serialization migration substituted run_reference")
        if self.record.run_reference != self.source_envelope.run_reference:
            raise ValueError("NII audit serialization migration decoded another run_reference")
