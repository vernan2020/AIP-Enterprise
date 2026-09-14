from __future__ import annotations

from aip.domain.irrbb.nii_audit_schema_evolution import NIIAuditSchemaEvolutionContract
from aip.domain.irrbb.nii_audit_serialization import (
    NIIRunAuditPayloadIntegrity,
    NIIRunAuditPayloadIntegrityError,
    NIIRunAuditRecordCodec,
    NIIRunAuditSerializationEnvelope,
    NIIRunAuditSerializationError,
)
from aip.domain.irrbb.nii_audit_serialization_migration import (
    NIIRunAuditAppliedSerializationMigration,
    NIIRunAuditPayloadMigrationTransformerResolver,
    NIIRunAuditSerializationMigrationError,
    NIIRunAuditSerializationMigrationResult,
)
from aip.domain.irrbb.services.nii_audit_schema_evolution_service import (
    NIIAuditSchemaEvolutionService,
)
from aip.domain.irrbb.services.nii_audit_serialization_service import (
    NIIRunAuditSerializationService,
)


class NIIRunAuditSerializationMigrationService:
    """Migrate historical serialized audit payloads through one explicit schema path."""

    @classmethod
    def migrate_and_decode(
        cls,
        *,
        envelope: NIIRunAuditSerializationEnvelope,
        schema_contract: NIIAuditSchemaEvolutionContract,
        transformer_resolver: NIIRunAuditPayloadMigrationTransformerResolver,
        codec: NIIRunAuditRecordCodec,
        integrity: NIIRunAuditPayloadIntegrity,
    ) -> NIIRunAuditSerializationMigrationResult:
        cls._validate_source_envelope(envelope=envelope, integrity=integrity)
        path = NIIAuditSchemaEvolutionService.migration_path(
            contract=schema_contract,
            source_version=envelope.schema_version,
        )

        current = envelope
        applied: list[NIIRunAuditAppliedSerializationMigration] = []
        for step in path:
            if current.schema_version != step.source:
                raise NIIRunAuditSerializationMigrationError(
                    "NII audit migration path does not match current envelope schema"
                )
            transformer = transformer_resolver.resolve(step=step)
            if transformer.step != step:
                raise NIIRunAuditSerializationMigrationError(
                    "NII audit migration resolver substituted schema migration step"
                )
            if not transformer.reference.strip():
                raise NIIRunAuditSerializationMigrationError(
                    "NII audit migration transformer reference is required"
                )

            source_digest = current.payload_digest
            migrated_payload = transformer.migrate(
                payload=current.payload,
                run_reference=current.run_reference,
            )
            if not migrated_payload:
                raise NIIRunAuditSerializationMigrationError(
                    "NII audit migration transformer produced an empty payload"
                )
            target_digest = integrity.digest(payload=migrated_payload)
            if not target_digest.strip():
                raise NIIRunAuditSerializationMigrationError(
                    "NII audit integrity boundary produced an empty migrated digest"
                )

            current = NIIRunAuditSerializationEnvelope(
                run_reference=current.run_reference,
                schema_version=step.target,
                codec_reference=current.codec_reference,
                integrity_reference=current.integrity_reference,
                payload=migrated_payload,
                payload_digest=target_digest,
            )
            applied.append(
                NIIRunAuditAppliedSerializationMigration(
                    step=step,
                    transformer_reference=transformer.reference,
                    source_payload_digest=source_digest,
                    target_payload_digest=target_digest,
                )
            )

        if current.schema_version != schema_contract.current_version:
            raise NIIRunAuditSerializationMigrationError(
                "NII audit migration did not reach current schema version"
            )

        record = NIIRunAuditSerializationService.decode(
            envelope=current,
            schema_contract=schema_contract,
            codec=codec,
            integrity=integrity,
        )
        return NIIRunAuditSerializationMigrationResult(
            source_envelope=envelope,
            current_envelope=current,
            applied_migrations=tuple(applied),
            record=record,
        )

    @staticmethod
    def _validate_source_envelope(
        *,
        envelope: NIIRunAuditSerializationEnvelope,
        integrity: NIIRunAuditPayloadIntegrity,
    ) -> None:
        if envelope.integrity_reference != integrity.reference:
            raise NIIRunAuditSerializationError(
                "NII audit envelope substituted integrity reference"
            )
        if not integrity.verify(
            payload=envelope.payload,
            expected_digest=envelope.payload_digest,
        ):
            raise NIIRunAuditPayloadIntegrityError(
                "NII audit historical payload failed integrity verification"
            )
