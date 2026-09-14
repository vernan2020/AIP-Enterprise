from __future__ import annotations

from aip.domain.irrbb.nii_audit_schema_evolution import NIIAuditSchemaEvolutionContract
from aip.domain.irrbb.nii_audit_serialization import (
    NIIRunAuditPayloadIntegrity,
    NIIRunAuditPayloadIntegrityError,
    NIIRunAuditRecordCodec,
    NIIRunAuditSerializationEnvelope,
    NIIRunAuditSerializationError,
    NIIRunAuditUnsupportedSchemaError,
)
from aip.domain.irrbb.nii_run_audit import NIIRunAuditRecord


class NIIRunAuditSerializationService:
    """Encode and decode audit records through explicit schema and integrity boundaries."""

    @staticmethod
    def encode(
        *,
        record: NIIRunAuditRecord,
        schema_contract: NIIAuditSchemaEvolutionContract,
        codec: NIIRunAuditRecordCodec,
        integrity: NIIRunAuditPayloadIntegrity,
    ) -> NIIRunAuditSerializationEnvelope:
        schema_version = schema_contract.current_version
        NIIRunAuditSerializationService._validate_boundary_references(
            codec=codec,
            integrity=integrity,
        )
        if schema_version not in codec.supported_schema_versions:
            raise NIIRunAuditUnsupportedSchemaError(
                "NII audit codec does not support the current schema version"
            )

        payload = codec.encode(record=record, schema_version=schema_version)
        if not payload:
            raise NIIRunAuditSerializationError("NII audit codec produced an empty payload")
        payload_digest = integrity.digest(payload=payload)
        if not payload_digest.strip():
            raise NIIRunAuditSerializationError(
                "NII audit integrity boundary produced an empty digest"
            )
        return NIIRunAuditSerializationEnvelope(
            run_reference=record.run_reference,
            schema_version=schema_version,
            codec_reference=codec.reference,
            integrity_reference=integrity.reference,
            payload=payload,
            payload_digest=payload_digest,
        )

    @staticmethod
    def decode(
        *,
        envelope: NIIRunAuditSerializationEnvelope,
        schema_contract: NIIAuditSchemaEvolutionContract,
        codec: NIIRunAuditRecordCodec,
        integrity: NIIRunAuditPayloadIntegrity,
    ) -> NIIRunAuditRecord:
        NIIRunAuditSerializationService._validate_boundary_references(
            codec=codec,
            integrity=integrity,
        )
        if envelope.codec_reference != codec.reference:
            raise NIIRunAuditSerializationError("NII audit envelope substituted codec reference")
        if envelope.integrity_reference != integrity.reference:
            raise NIIRunAuditSerializationError(
                "NII audit envelope substituted integrity reference"
            )
        if envelope.schema_version not in schema_contract.readable_versions:
            raise NIIRunAuditUnsupportedSchemaError(
                "NII audit envelope schema version is not declared readable"
            )
        if envelope.schema_version not in codec.supported_schema_versions:
            raise NIIRunAuditUnsupportedSchemaError(
                "NII audit codec does not support the envelope schema version"
            )
        if not integrity.verify(
            payload=envelope.payload,
            expected_digest=envelope.payload_digest,
        ):
            raise NIIRunAuditPayloadIntegrityError(
                "NII audit serialized payload failed integrity verification"
            )

        record = codec.decode(
            payload=envelope.payload,
            schema_version=envelope.schema_version,
        )
        if record.run_reference != envelope.run_reference:
            raise NIIRunAuditSerializationError(
                "NII audit decoded record substituted run_reference"
            )
        return record

    @staticmethod
    def _validate_boundary_references(
        *,
        codec: NIIRunAuditRecordCodec,
        integrity: NIIRunAuditPayloadIntegrity,
    ) -> None:
        if not codec.reference.strip():
            raise NIIRunAuditSerializationError("NII audit codec reference is required")
        if not codec.supported_schema_versions:
            raise NIIRunAuditSerializationError(
                "NII audit codec must declare supported schema versions"
            )
        if not integrity.reference.strip():
            raise NIIRunAuditSerializationError("NII audit integrity reference is required")
