from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaMigrationStep,
    NIIAuditSchemaVersion,
)
from aip.domain.irrbb.nii_audit_serialization import (
    NIIRunAuditPayloadIntegrity,
    NIIRunAuditRecordCodec,
    NIIRunAuditSerializationError,
    NIIRunAuditUnsupportedSchemaError,
)
from aip.domain.irrbb.nii_audit_serialization_compatibility import (
    NIIRunAuditSerializationCompatibilityError,
)
from aip.domain.irrbb.nii_audit_serialization_migration import (
    NIIRunAuditPayloadMigrationTransformer,
)
from aip.domain.irrbb.nii_run_audit import NIIRunAuditRecord
from aip.domain.irrbb.services.nii_audit_serialization_compatibility_service import (
    NIIRunAuditSerializationCompatibilityService,
)

_V1 = NIIAuditSchemaVersion("aip.irrbb.nii-audit", 1)
_V2 = NIIAuditSchemaVersion("aip.irrbb.nii-audit", 2)
_V3 = NIIAuditSchemaVersion("aip.irrbb.nii-audit", 3)
_STEP_12 = NIIAuditSchemaMigrationStep(
    source=_V1,
    target=_V2,
    source_reference="architecture:phase35:v1-v2",
)
_STEP_23 = NIIAuditSchemaMigrationStep(
    source=_V2,
    target=_V3,
    source_reference="architecture:phase35:v2-v3",
)


class _Codec:
    reference = "codec:test:v3"
    supported_schema_versions = frozenset({_V3})

    def encode(
        self,
        *,
        record: NIIRunAuditRecord,
        schema_version: NIIAuditSchemaVersion,
    ) -> bytes:
        raise AssertionError("encode is not used by static compatibility certification")

    def decode(
        self,
        *,
        payload: bytes,
        schema_version: NIIAuditSchemaVersion,
    ) -> NIIRunAuditRecord:
        raise AssertionError("decode is not used by static compatibility certification")


class _Integrity:
    reference = "integrity:test:v1"

    def digest(self, *, payload: bytes) -> str:
        raise AssertionError("digest is not used by static compatibility certification")

    def verify(self, *, payload: bytes, expected_digest: str) -> bool:
        raise AssertionError("verify is not used by static compatibility certification")


@dataclass(frozen=True, slots=True)
class _Transformer:
    step: NIIAuditSchemaMigrationStep
    reference: str

    def migrate(self, *, payload: bytes, run_reference: str) -> bytes:
        raise AssertionError("migrate is not used by static compatibility certification")


class _Resolver:
    def __init__(
        self,
        transformers: dict[NIIAuditSchemaMigrationStep, _Transformer] | None = None,
    ) -> None:
        self.transformers = transformers or {
            _STEP_12: _Transformer(_STEP_12, "transformer:test:v1-v2"),
            _STEP_23: _Transformer(_STEP_23, "transformer:test:v2-v3"),
        }
        self.calls: list[NIIAuditSchemaMigrationStep] = []

    def resolve(
        self,
        *,
        step: NIIAuditSchemaMigrationStep,
    ) -> NIIRunAuditPayloadMigrationTransformer:
        self.calls.append(step)
        return cast(NIIRunAuditPayloadMigrationTransformer, self.transformers[step])


def _contract() -> NIIAuditSchemaEvolutionContract:
    return NIIAuditSchemaEvolutionContract(
        current_version=_V3,
        readable_versions=frozenset({_V1, _V2, _V3}),
        migration_steps=(_STEP_12, _STEP_23),
        source_reference="architecture:phase35:test",
    )


def test_certifies_complete_declared_readable_perimeter() -> None:
    resolver = _Resolver()

    certificate = NIIRunAuditSerializationCompatibilityService.certify(
        schema_contract=_contract(),
        codec=cast(NIIRunAuditRecordCodec, _Codec()),
        integrity=cast(NIIRunAuditPayloadIntegrity, _Integrity()),
        transformer_resolver=resolver,
    )

    assert certificate.codec_reference == _Codec.reference
    assert certificate.integrity_reference == _Integrity.reference
    assert tuple(
        entry.source_version for entry in certificate.readable_schema_compatibility
    ) == (_V1, _V2, _V3)

    v1, v2, v3 = certificate.readable_schema_compatibility
    assert v1.migration_steps == (_STEP_12, _STEP_23)
    assert v1.transformer_references == (
        "transformer:test:v1-v2",
        "transformer:test:v2-v3",
    )
    assert v2.migration_steps == (_STEP_23,)
    assert v2.transformer_references == ("transformer:test:v2-v3",)
    assert v3.migration_steps == ()
    assert v3.transformer_references == ()
    assert resolver.calls == [_STEP_12, _STEP_23]


def test_codec_only_needs_to_support_current_schema() -> None:
    certificate = NIIRunAuditSerializationCompatibilityService.certify(
        schema_contract=_contract(),
        codec=cast(NIIRunAuditRecordCodec, _Codec()),
        integrity=cast(NIIRunAuditPayloadIntegrity, _Integrity()),
        transformer_resolver=_Resolver(),
    )

    assert certificate.schema_contract.current_version == _V3
    assert _V1 not in _Codec.supported_schema_versions
    assert _V2 not in _Codec.supported_schema_versions


def test_rejects_codec_without_current_schema_support() -> None:
    class _HistoricalOnlyCodec(_Codec):
        supported_schema_versions = frozenset({_V1, _V2})

    with pytest.raises(NIIRunAuditUnsupportedSchemaError):
        NIIRunAuditSerializationCompatibilityService.certify(
            schema_contract=_contract(),
            codec=cast(NIIRunAuditRecordCodec, _HistoricalOnlyCodec()),
            integrity=cast(NIIRunAuditPayloadIntegrity, _Integrity()),
            transformer_resolver=_Resolver(),
        )


def test_rejects_blank_boundary_references() -> None:
    class _BlankCodec(_Codec):
        reference = " "

    class _BlankIntegrity(_Integrity):
        reference = " "

    with pytest.raises(NIIRunAuditSerializationError):
        NIIRunAuditSerializationCompatibilityService.certify(
            schema_contract=_contract(),
            codec=cast(NIIRunAuditRecordCodec, _BlankCodec()),
            integrity=cast(NIIRunAuditPayloadIntegrity, _Integrity()),
            transformer_resolver=_Resolver(),
        )

    with pytest.raises(NIIRunAuditSerializationError):
        NIIRunAuditSerializationCompatibilityService.certify(
            schema_contract=_contract(),
            codec=cast(NIIRunAuditRecordCodec, _Codec()),
            integrity=cast(NIIRunAuditPayloadIntegrity, _BlankIntegrity()),
            transformer_resolver=_Resolver(),
        )


def test_rejects_transformer_bound_to_another_step() -> None:
    wrong = _Transformer(
        step=_STEP_23,
        reference="transformer:test:wrong",
    )
    resolver = _Resolver(transformers={_STEP_12: wrong, _STEP_23: wrong})

    with pytest.raises(NIIRunAuditSerializationCompatibilityError):
        NIIRunAuditSerializationCompatibilityService.certify(
            schema_contract=_contract(),
            codec=cast(NIIRunAuditRecordCodec, _Codec()),
            integrity=cast(NIIRunAuditPayloadIntegrity, _Integrity()),
            transformer_resolver=resolver,
        )


def test_rejects_blank_transformer_reference() -> None:
    resolver = _Resolver(
        transformers={
            _STEP_12: _Transformer(_STEP_12, " "),
            _STEP_23: _Transformer(_STEP_23, "transformer:test:v2-v3"),
        }
    )

    with pytest.raises(NIIRunAuditSerializationCompatibilityError):
        NIIRunAuditSerializationCompatibilityService.certify(
            schema_contract=_contract(),
            codec=cast(NIIRunAuditRecordCodec, _Codec()),
            integrity=cast(NIIRunAuditPayloadIntegrity, _Integrity()),
            transformer_resolver=resolver,
        )


def test_ambiguous_schema_contract_cannot_be_certified() -> None:
    direct = NIIAuditSchemaMigrationStep(
        source=_V1,
        target=_V3,
        source_reference="architecture:phase35:v1-v3",
    )
    ambiguous = NIIAuditSchemaEvolutionContract(
        current_version=_V3,
        readable_versions=frozenset({_V1, _V2, _V3}),
        migration_steps=(_STEP_12, _STEP_23, direct),
        source_reference="architecture:phase35:ambiguous",
    )

    with pytest.raises(ValueError, match="ambiguous"):
        NIIRunAuditSerializationCompatibilityService.certify(
            schema_contract=ambiguous,
            codec=cast(NIIRunAuditRecordCodec, _Codec()),
            integrity=cast(NIIRunAuditPayloadIntegrity, _Integrity()),
            transformer_resolver=_Resolver(),
        )


def test_current_only_contract_does_not_resolve_transformers() -> None:
    contract = NIIAuditSchemaEvolutionContract(
        current_version=_V3,
        readable_versions=frozenset({_V3}),
        migration_steps=(),
        source_reference="architecture:phase35:current-only",
    )
    resolver = _Resolver(transformers={})

    certificate = NIIRunAuditSerializationCompatibilityService.certify(
        schema_contract=contract,
        codec=cast(NIIRunAuditRecordCodec, _Codec()),
        integrity=cast(NIIRunAuditPayloadIntegrity, _Integrity()),
        transformer_resolver=resolver,
    )

    assert resolver.calls == []
    assert certificate.readable_schema_compatibility[0].migration_steps == ()
