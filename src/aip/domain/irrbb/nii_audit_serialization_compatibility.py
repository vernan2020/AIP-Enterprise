from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaMigrationStep,
    NIIAuditSchemaVersion,
)


class NIIRunAuditSerializationCompatibilityError(ValueError):
    """Raised when a serialization configuration cannot be certified compatible."""


@dataclass(frozen=True, slots=True)
class NIIAuditReadableSchemaCompatibility:
    """Certified migration coverage for one declared readable schema version."""

    source_version: NIIAuditSchemaVersion
    migration_steps: tuple[NIIAuditSchemaMigrationStep, ...]
    transformer_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.migration_steps) != len(self.transformer_references):
            raise ValueError(
                "NII audit compatibility migration steps and transformer references must align"
            )
        if any(not reference.strip() for reference in self.transformer_references):
            raise ValueError("NII audit compatibility transformer reference is required")
        if self.migration_steps and self.migration_steps[0].source != self.source_version:
            raise ValueError("NII audit compatibility path starts from another schema version")
        for previous, current in zip(self.migration_steps, self.migration_steps[1:]):
            if previous.target != current.source:
                raise ValueError("NII audit compatibility migration path is not contiguous")


@dataclass(frozen=True, slots=True)
class NIIRunAuditSerializationCompatibilityCertificate:
    """Static proof that one serialization configuration covers its readable perimeter."""

    schema_contract: NIIAuditSchemaEvolutionContract
    codec_reference: str
    integrity_reference: str
    readable_schema_compatibility: tuple[NIIAuditReadableSchemaCompatibility, ...]

    def __post_init__(self) -> None:
        if not self.codec_reference.strip():
            raise ValueError("NII audit compatibility codec_reference is required")
        if not self.integrity_reference.strip():
            raise ValueError("NII audit compatibility integrity_reference is required")
        source_versions = tuple(
            item.source_version for item in self.readable_schema_compatibility
        )
        if len(source_versions) != len(set(source_versions)):
            raise ValueError("Duplicate NII audit readable schema compatibility entry")
        if set(source_versions) != set(self.schema_contract.readable_versions):
            raise ValueError(
                "NII audit compatibility certificate does not cover the declared readable perimeter"
            )
        for item in self.readable_schema_compatibility:
            if item.source_version == self.schema_contract.current_version:
                if item.migration_steps or item.transformer_references:
                    raise ValueError(
                        "Current NII audit schema compatibility cannot require migration"
                    )
                continue
            if not item.migration_steps:
                raise ValueError(
                    "Historical NII audit schema compatibility requires a migration path"
                )
            if item.migration_steps[-1].target != self.schema_contract.current_version:
                raise ValueError(
                    "NII audit compatibility migration path does not reach current schema"
                )
