from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaMigrationStep,
    NIIAuditSchemaVersion,
)
from aip.domain.irrbb.nii_audit_serialization import (
    NIIRunAuditPayloadIntegrityError,
    NIIRunAuditSerializationEnvelope,
)
from aip.domain.irrbb.nii_audit_serialization_migration import (
    NIIRunAuditSerializationMigrationError,
)
from aip.domain.irrbb.nii_run_audit import NIIRunAuditRecord
from aip.domain.irrbb.services.nii_audit_serialization_migration_service import (
    NIIRunAuditSerializationMigrationService,
)


_V1 = NIIAuditSchemaVersion("aip.irrbb.nii-audit", 1)
_V2 = NIIAuditSchemaVersion("aip.irrbb.nii-audit", 2)
_STEP = NIIAuditSchemaMigrationStep(
    source=_V1,
    target=_V2,
    source_reference="architecture:phase34:v1-to-v2",
)


@dataclass(frozen=True, slots=True)
class _Record:
    run_reference: str


class _Codec:
    reference = "codec:test:v2"
    supported_schema_versions = frozenset({_V2})

    def __init__(self, record: _Record) -> None:
        self.record = record

    def encode(self, *, record: NIIRunAuditRecord, schema_version: NIIAuditSchemaVersion) -> bytes:
        raise AssertionError("encode is not used in migration tests")

    def decode(self, *, payload: bytes, schema_version: NIIAuditSchemaVersion) -> NIIRunAuditRecord:
        assert schema_version == _V2
        assert payload == f"v2:{self.record.run_reference}".encode()
        return cast(NIIRunAuditRecord, self.record)


class _Integrity:
    reference = "integrity:test-sha256:v1"

    def digest(self, *, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def verify(self, *, payload: bytes, expected_digest: str) -> bool:
        return self.digest(payload=payload) == expected_digest


class _Transformer:
    reference = "transformer:test:v1-to-v2"
    step = _STEP

    def migrate(self, *, payload: bytes, run_reference: str) -> bytes:
        assert payload == f"v1:{run_reference}".encode()
        return f"v2:{run_reference}".encode()


class _Resolver:
    def __init__(self, transformer: _Transformer | None = None) -> None:
        self.transformer = transformer or _Transformer()
        self.calls = 0

    def resolve(self, *, step: NIIAuditSchemaMigrationStep) -> _Transformer:
        self.calls += 1
        assert step == _STEP
        return self.transformer


def _contract() -> NIIAuditSchemaEvolutionContract:
    return NIIAuditSchemaEvolutionContract(
        current_version=_V2,
        readable_versions=frozenset({_V1, _V2}),
        migration_steps=(_STEP,),
        source_reference="architecture:phase34:test",
    )


def _envelope(*, run_reference: str = "nii-run:phase34") -> NIIRunAuditSerializationEnvelope:
    payload = f"v1:{run_reference}".encode()
    integrity = _Integrity()
    return NIIRunAuditSerializationEnvelope(
        run_reference=run_reference,
        schema_version=_V1,
        codec_reference=_Codec.reference,
        integrity_reference=integrity.reference,
        payload=payload,
        payload_digest=integrity.digest(payload=payload),
    )


def test_migrates_historical_envelope_and_decodes_current_record() -> None:
    envelope = _envelope()
    resolver = _Resolver()
    record = _Record(run_reference=envelope.run_reference)

    result = NIIRunAuditSerializationMigrationService.migrate_and_decode(
        envelope=envelope,
        schema_contract=_contract(),
        transformer_resolver=resolver,
        codec=_Codec(record),
        integrity=_Integrity(),
    )

    assert result.source_envelope == envelope
    assert result.current_envelope.schema_version == _V2
    assert result.current_envelope.run_reference == envelope.run_reference
    assert result.record.run_reference == envelope.run_reference
    assert resolver.calls == 1
    assert len(result.applied_migrations) == 1
    applied = result.applied_migrations[0]
    assert applied.step == _STEP
    assert applied.transformer_reference == _Transformer.reference
    assert applied.source_payload_digest == envelope.payload_digest
    assert applied.target_payload_digest == result.current_envelope.payload_digest


def test_rejects_tampered_historical_payload_before_resolving_transformer() -> None:
    envelope = _envelope()
    tampered = NIIRunAuditSerializationEnvelope(
        run_reference=envelope.run_reference,
        schema_version=envelope.schema_version,
        codec_reference=envelope.codec_reference,
        integrity_reference=envelope.integrity_reference,
        payload=envelope.payload + b":tampered",
        payload_digest=envelope.payload_digest,
    )
    resolver = _Resolver()

    with pytest.raises(NIIRunAuditPayloadIntegrityError):
        NIIRunAuditSerializationMigrationService.migrate_and_decode(
            envelope=tampered,
            schema_contract=_contract(),
            transformer_resolver=resolver,
            codec=_Codec(_Record(run_reference=envelope.run_reference)),
            integrity=_Integrity(),
        )

    assert resolver.calls == 0


def test_rejects_transformer_bound_to_another_step() -> None:
    wrong_step = NIIAuditSchemaMigrationStep(
        source=_V1,
        target=NIIAuditSchemaVersion("aip.irrbb.nii-audit", 3),
        source_reference="architecture:wrong-step",
    )

    class _WrongTransformer(_Transformer):
        step = wrong_step

    resolver = _Resolver(transformer=_WrongTransformer())
    envelope = _envelope()

    with pytest.raises(NIIRunAuditSerializationMigrationError):
        NIIRunAuditSerializationMigrationService.migrate_and_decode(
            envelope=envelope,
            schema_contract=_contract(),
            transformer_resolver=resolver,
            codec=_Codec(_Record(run_reference=envelope.run_reference)),
            integrity=_Integrity(),
        )


def test_current_schema_decodes_without_invoking_migration_resolver() -> None:
    run_reference = "nii-run:phase34:current"
    payload = f"v2:{run_reference}".encode()
    integrity = _Integrity()
    envelope = NIIRunAuditSerializationEnvelope(
        run_reference=run_reference,
        schema_version=_V2,
        codec_reference=_Codec.reference,
        integrity_reference=integrity.reference,
        payload=payload,
        payload_digest=integrity.digest(payload=payload),
    )
    resolver = _Resolver()

    result = NIIRunAuditSerializationMigrationService.migrate_and_decode(
        envelope=envelope,
        schema_contract=_contract(),
        transformer_resolver=resolver,
        codec=_Codec(_Record(run_reference=run_reference)),
        integrity=integrity,
    )

    assert result.current_envelope == envelope
    assert result.applied_migrations == ()
    assert resolver.calls == 0
