from __future__ import annotations

from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaMigrationStep,
)
from aip.domain.irrbb.nii_audit_serialization import (
    NIIRunAuditPayloadIntegrity,
    NIIRunAuditRecordCodec,
    NIIRunAuditSerializationError,
    NIIRunAuditUnsupportedSchemaError,
)
from aip.domain.irrbb.nii_audit_serialization_compatibility import (
    NIIAuditReadableSchemaCompatibility,
    NIIRunAuditSerializationCompatibilityCertificate,
    NIIRunAuditSerializationCompatibilityError,
)
from aip.domain.irrbb.nii_audit_serialization_migration import (
    NIIRunAuditPayloadMigrationTransformerResolver,
)
from aip.domain.irrbb.services.nii_audit_schema_evolution_service import (
    NIIAuditSchemaEvolutionService,
)


class NIIRunAuditSerializationCompatibilityService:
    """Statically certify one NII audit serialization configuration."""

    @classmethod
    def certify(
        cls,
        *,
        schema_contract: NIIAuditSchemaEvolutionContract,
        codec: NIIRunAuditRecordCodec,
        integrity: NIIRunAuditPayloadIntegrity,
        transformer_resolver: NIIRunAuditPayloadMigrationTransformerResolver,
    ) -> NIIRunAuditSerializationCompatibilityCertificate:
        NIIAuditSchemaEvolutionService.validate_contract(contract=schema_contract)
        cls._validate_boundaries(
            schema_contract=schema_contract,
            codec=codec,
            integrity=integrity,
        )

        paths = {
            source_version: NIIAuditSchemaEvolutionService.migration_path(
                contract=schema_contract,
                source_version=source_version,
            )
            for source_version in sorted(schema_contract.readable_versions)
        }
        used_steps = {step for path in paths.values() for step in path}
        required_steps = tuple(
            step for step in schema_contract.migration_steps if step in used_steps
        )

        transformer_references: dict[NIIAuditSchemaMigrationStep, str] = {}
        for step in required_steps:
            transformer = transformer_resolver.resolve(step=step)
            if transformer.step != step:
                raise NIIRunAuditSerializationCompatibilityError(
                    "NII audit compatibility resolver substituted schema migration step"
                )
            if not transformer.reference.strip():
                raise NIIRunAuditSerializationCompatibilityError(
                    "NII audit compatibility transformer reference is required"
                )
            transformer_references[step] = transformer.reference

        entries = tuple(
            NIIAuditReadableSchemaCompatibility(
                source_version=source_version,
                migration_steps=path,
                transformer_references=tuple(
                    transformer_references[step] for step in path
                ),
            )
            for source_version, path in paths.items()
        )
        return NIIRunAuditSerializationCompatibilityCertificate(
            schema_contract=schema_contract,
            codec_reference=codec.reference,
            integrity_reference=integrity.reference,
            readable_schema_compatibility=entries,
        )

    @staticmethod
    def _validate_boundaries(
        *,
        schema_contract: NIIAuditSchemaEvolutionContract,
        codec: NIIRunAuditRecordCodec,
        integrity: NIIRunAuditPayloadIntegrity,
    ) -> None:
        if not codec.reference.strip():
            raise NIIRunAuditSerializationError("NII audit codec reference is required")
        if not codec.supported_schema_versions:
            raise NIIRunAuditSerializationError(
                "NII audit codec must declare supported schema versions"
            )
        if schema_contract.current_version not in codec.supported_schema_versions:
            raise NIIRunAuditUnsupportedSchemaError(
                "NII audit codec does not support the current schema version"
            )
        if not integrity.reference.strip():
            raise NIIRunAuditSerializationError("NII audit integrity reference is required")
