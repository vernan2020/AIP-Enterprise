from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

import pytest

from aip.domain.irrbb.models import (
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
)
from aip.domain.irrbb.nii import (
    NIIBalanceSheetAssumption,
    NIIProjectionBasis,
    NIIShockTiming,
)
from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaVersion,
)
from aip.domain.irrbb.nii_audit_serialization import (
    NIIRunAuditPayloadIntegrityError,
    NIIRunAuditSerializationEnvelope,
    NIIRunAuditSerializationError,
    NIIRunAuditUnsupportedSchemaError,
)
from aip.domain.irrbb.nii_run_audit import NIIRunAuditRecord
from aip.domain.irrbb.nii_run_specification import (
    NIIMethodologyRunResult,
    NIIMethodologyRunSpecification,
)
from aip.domain.irrbb.services.nii_audit_serialization_service import (
    NIIRunAuditSerializationService,
)
from aip.domain.irrbb.services.nii_run_reproducibility_service import (
    NIIRunReproducibilityService,
)
from aip.shared.money import Currency


@dataclass(frozen=True, slots=True)
class _EvaluationBinding:
    basis: NIIProjectionBasis
    reporting_currency: Currency
    required_stressed_scenarios: tuple[IRRBBScenario, ...]


def _record(*, run_reference: str = "nii-run:phase33:primary") -> NIIRunAuditRecord:
    basis = NIIProjectionBasis(
        methodology=IRRBBMethodologyProfile(
            code="INTERNAL-NII",
            version="2026.09.11",
            status=IRRBBMethodologyStatus.INTERNAL,
            source_reference="policy:nii-methodology:v1",
        ),
        valuation_date=date(2026, 9, 11),
        horizon_end_date=date(2027, 9, 11),
        balance_sheet_assumption=NIIBalanceSheetAssumption.CONSTANT,
        shock_timing=NIIShockTiming.INSTANTANEOUS,
        source_reference="basis:approved:v1",
    )
    specification = NIIMethodologyRunSpecification(
        run_reference=run_reference,
        basis=basis,
        reporting_currency=Currency.CRC,
        stressed_scenarios=(IRRBBScenario.PARALLEL_UP, IRRBBScenario.PARALLEL_DOWN),
        policy_references=("policy:nii-methodology:v1", "policy:scenario-set:v1"),
        evidence_references=("evidence:portfolio-cutoff:2026-09-11",),
    )
    result = NIIMethodologyRunResult(
        specification=specification,
        evaluation=_EvaluationBinding(
            basis=basis,
            reporting_currency=Currency.CRC,
            required_stressed_scenarios=specification.stressed_scenarios,
        ),  # type: ignore[arg-type]
    )
    return NIIRunAuditRecord(
        specification=specification,
        manifest=NIIRunReproducibilityService.build(specification=specification),
        result=result,
    )


_V1 = NIIAuditSchemaVersion(schema_reference="aip.irrbb.nii-audit", version=1)
_V2 = NIIAuditSchemaVersion(schema_reference="aip.irrbb.nii-audit", version=2)


def _contract() -> NIIAuditSchemaEvolutionContract:
    return NIIAuditSchemaEvolutionContract(
        current_version=_V2,
        readable_versions=frozenset({_V1, _V2}),
        migration_steps=(),
        source_reference="architecture:phase33:test",
    )


class _MemoryCodec:
    reference = "codec:test-memory:v1"

    def __init__(self, *, supported: frozenset[NIIAuditSchemaVersion] | None = None) -> None:
        self._supported = supported or frozenset({_V1, _V2})
        self._records: dict[bytes, NIIRunAuditRecord] = {}

    @property
    def supported_schema_versions(self) -> frozenset[NIIAuditSchemaVersion]:
        return self._supported

    def encode(self, *, record: NIIRunAuditRecord, schema_version: NIIAuditSchemaVersion) -> bytes:
        payload = f"{schema_version.version}:{record.run_reference}".encode()
        self._records[payload] = record
        return payload

    def decode(self, *, payload: bytes, schema_version: NIIAuditSchemaVersion) -> NIIRunAuditRecord:
        return self._records[payload]


class _Sha256Integrity:
    reference = "integrity:test-sha256:v1"

    def digest(self, *, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def verify(self, *, payload: bytes, expected_digest: str) -> bool:
        return self.digest(payload=payload) == expected_digest


def test_encode_and_decode_round_trip_binds_current_schema_and_run_reference() -> None:
    record = _record()
    codec = _MemoryCodec()
    integrity = _Sha256Integrity()

    envelope = NIIRunAuditSerializationService.encode(
        record=record,
        schema_contract=_contract(),
        codec=codec,
        integrity=integrity,
    )
    decoded = NIIRunAuditSerializationService.decode(
        envelope=envelope,
        schema_contract=_contract(),
        codec=codec,
        integrity=integrity,
    )

    assert envelope.schema_version == _V2
    assert envelope.run_reference == record.run_reference
    assert decoded == record


def test_encode_rejects_codec_without_current_schema_support() -> None:
    with pytest.raises(NIIRunAuditUnsupportedSchemaError):
        NIIRunAuditSerializationService.encode(
            record=_record(),
            schema_contract=_contract(),
            codec=_MemoryCodec(supported=frozenset({_V1})),
            integrity=_Sha256Integrity(),
        )


def test_decode_rejects_tampered_payload_before_codec_decode() -> None:
    record = _record()
    codec = _MemoryCodec()
    integrity = _Sha256Integrity()
    envelope = NIIRunAuditSerializationService.encode(
        record=record,
        schema_contract=_contract(),
        codec=codec,
        integrity=integrity,
    )
    tampered = NIIRunAuditSerializationEnvelope(
        run_reference=envelope.run_reference,
        schema_version=envelope.schema_version,
        codec_reference=envelope.codec_reference,
        integrity_reference=envelope.integrity_reference,
        payload=envelope.payload + b":tampered",
        payload_digest=envelope.payload_digest,
    )

    with pytest.raises(NIIRunAuditPayloadIntegrityError):
        NIIRunAuditSerializationService.decode(
            envelope=tampered,
            schema_contract=_contract(),
            codec=codec,
            integrity=integrity,
        )


def test_decode_rejects_substituted_codec_reference() -> None:
    record = _record()
    codec = _MemoryCodec()
    integrity = _Sha256Integrity()
    envelope = NIIRunAuditSerializationService.encode(
        record=record,
        schema_contract=_contract(),
        codec=codec,
        integrity=integrity,
    )
    substituted = NIIRunAuditSerializationEnvelope(
        run_reference=envelope.run_reference,
        schema_version=envelope.schema_version,
        codec_reference="codec:other:v1",
        integrity_reference=envelope.integrity_reference,
        payload=envelope.payload,
        payload_digest=envelope.payload_digest,
    )

    with pytest.raises(NIIRunAuditSerializationError):
        NIIRunAuditSerializationService.decode(
            envelope=substituted,
            schema_contract=_contract(),
            codec=codec,
            integrity=integrity,
        )


def test_decode_rejects_schema_not_declared_readable() -> None:
    record = _record()
    codec = _MemoryCodec(
        supported=frozenset({_V1, _V2, NIIAuditSchemaVersion("aip.irrbb.nii-audit", 3)})
    )
    integrity = _Sha256Integrity()
    payload = codec.encode(
        record=record, schema_version=NIIAuditSchemaVersion("aip.irrbb.nii-audit", 3)
    )
    envelope = NIIRunAuditSerializationEnvelope(
        run_reference=record.run_reference,
        schema_version=NIIAuditSchemaVersion("aip.irrbb.nii-audit", 3),
        codec_reference=codec.reference,
        integrity_reference=integrity.reference,
        payload=payload,
        payload_digest=integrity.digest(payload=payload),
    )

    with pytest.raises(NIIRunAuditUnsupportedSchemaError):
        NIIRunAuditSerializationService.decode(
            envelope=envelope,
            schema_contract=_contract(),
            codec=codec,
            integrity=integrity,
        )


def test_decode_rejects_run_reference_substitution() -> None:
    stored_record = _record(run_reference="nii-run:phase33:stored")
    codec = _MemoryCodec()
    integrity = _Sha256Integrity()
    envelope = NIIRunAuditSerializationService.encode(
        record=stored_record,
        schema_contract=_contract(),
        codec=codec,
        integrity=integrity,
    )
    substituted = NIIRunAuditSerializationEnvelope(
        run_reference="nii-run:phase33:other",
        schema_version=envelope.schema_version,
        codec_reference=envelope.codec_reference,
        integrity_reference=envelope.integrity_reference,
        payload=envelope.payload,
        payload_digest=envelope.payload_digest,
    )

    with pytest.raises(NIIRunAuditSerializationError):
        NIIRunAuditSerializationService.decode(
            envelope=substituted,
            schema_contract=_contract(),
            codec=codec,
            integrity=integrity,
        )
