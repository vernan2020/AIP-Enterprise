from __future__ import annotations

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
from aip.domain.irrbb.nii_run_audit import (
    NIIRunAuditConflictError,
    NIIRunAuditRecord,
    NIIRunAuditRepositoryPutResult,
    NIIRunAuditWriteStatus,
)
from aip.domain.irrbb.nii_run_specification import (
    NIIMethodologyRunResult,
    NIIMethodologyRunSpecification,
)
from aip.domain.irrbb.services.nii_run_audit_service import NIIRunAuditService
from aip.domain.irrbb.services.nii_run_reproducibility_service import (
    NIIRunReproducibilityService,
)
from aip.shared.money import Currency


@dataclass(frozen=True, slots=True)
class _EvaluationBinding:
    basis: NIIProjectionBasis
    reporting_currency: Currency
    required_stressed_scenarios: tuple[IRRBBScenario, ...]
    marker: str


def _basis(*, source_reference: str = "basis:approved:v1") -> NIIProjectionBasis:
    return NIIProjectionBasis(
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
        source_reference=source_reference,
    )


def _specification(
    *,
    run_reference: str = "nii-run:2026-09-11:001",
    basis_source_reference: str = "basis:approved:v1",
) -> NIIMethodologyRunSpecification:
    return NIIMethodologyRunSpecification(
        run_reference=run_reference,
        basis=_basis(source_reference=basis_source_reference),
        reporting_currency=Currency.CRC,
        stressed_scenarios=(IRRBBScenario.PARALLEL_UP, IRRBBScenario.PARALLEL_DOWN),
        policy_references=("policy:nii-methodology:v1", "policy:scenario-set:v1"),
        evidence_references=("evidence:portfolio-cutoff:2026-09-11",),
    )


def _record(
    *,
    run_reference: str = "nii-run:2026-09-11:001",
    basis_source_reference: str = "basis:approved:v1",
    result_marker: str = "result:v1",
) -> NIIRunAuditRecord:
    specification = _specification(
        run_reference=run_reference,
        basis_source_reference=basis_source_reference,
    )
    evaluation = _EvaluationBinding(
        basis=specification.basis,
        reporting_currency=specification.reporting_currency,
        required_stressed_scenarios=specification.stressed_scenarios,
        marker=result_marker,
    )
    result = NIIMethodologyRunResult(
        specification=specification,
        evaluation=evaluation,  # type: ignore[arg-type]
    )
    return NIIRunAuditRecord(
        specification=specification,
        manifest=NIIRunReproducibilityService.build(specification=specification),
        result=result,
    )


class _MemoryRepository:
    def __init__(self) -> None:
        self.records: dict[str, NIIRunAuditRecord] = {}

    def get_by_run_reference(self, *, run_reference: str) -> NIIRunAuditRecord | None:
        return self.records.get(run_reference)

    def put_if_absent(self, *, record: NIIRunAuditRecord) -> NIIRunAuditRepositoryPutResult:
        existing = self.records.get(record.run_reference)
        if existing is not None:
            return NIIRunAuditRepositoryPutResult(created=False, record=existing)
        self.records[record.run_reference] = record
        return NIIRunAuditRepositoryPutResult(created=True, record=record)


class _SubstitutingRepository:
    def __init__(self, *, substituted: NIIRunAuditRecord) -> None:
        self.substituted = substituted

    def get_by_run_reference(self, *, run_reference: str) -> NIIRunAuditRecord | None:
        return None

    def put_if_absent(self, *, record: NIIRunAuditRecord) -> NIIRunAuditRepositoryPutResult:
        return NIIRunAuditRepositoryPutResult(created=True, record=self.substituted)


def test_first_write_is_stored_and_exact_repeat_is_idempotent() -> None:
    repository = _MemoryRepository()
    service = NIIRunAuditService(repository=repository)
    record = _record()

    first = service.store(record=record)
    second = service.store(record=record)

    assert first.status is NIIRunAuditWriteStatus.STORED
    assert second.status is NIIRunAuditWriteStatus.IDEMPOTENT
    assert service.get(run_reference=record.run_reference) == record


def test_same_run_reference_with_different_methodology_fingerprint_conflicts() -> None:
    repository = _MemoryRepository()
    service = NIIRunAuditService(repository=repository)
    service.store(record=_record())

    with pytest.raises(NIIRunAuditConflictError, match="methodology fingerprint differs"):
        service.store(record=_record(basis_source_reference="basis:approved:v2"))


def test_same_run_reference_and_fingerprint_with_different_result_conflicts() -> None:
    repository = _MemoryRepository()
    service = NIIRunAuditService(repository=repository)
    service.store(record=_record(result_marker="result:v1"))

    with pytest.raises(NIIRunAuditConflictError, match="audit payload differs"):
        service.store(record=_record(result_marker="result:v2"))


def test_same_methodology_fingerprint_with_different_run_reference_is_allowed() -> None:
    repository = _MemoryRepository()
    service = NIIRunAuditService(repository=repository)
    first = _record(run_reference="nii-run:001")
    second = _record(run_reference="nii-run:002")

    assert first.specification_fingerprint == second.specification_fingerprint
    assert service.store(record=first).status is NIIRunAuditWriteStatus.STORED
    assert service.store(record=second).status is NIIRunAuditWriteStatus.STORED


def test_manifest_mismatch_fails_before_repository_write() -> None:
    repository = _MemoryRepository()
    service = NIIRunAuditService(repository=repository)
    record = _record()
    alternate_specification = _specification(basis_source_reference="basis:approved:v2")
    mismatched = NIIRunAuditRecord(
        specification=record.specification,
        manifest=NIIRunReproducibilityService.build(specification=alternate_specification),
        result=record.result,
    )

    with pytest.raises(ValueError, match="manifest does not match"):
        service.store(record=mismatched)

    assert repository.records == {}


def test_repository_substitution_after_create_fails_closed() -> None:
    record = _record()
    substituted = _record(
        run_reference=record.run_reference,
        basis_source_reference="basis:approved:v2",
    )
    service = NIIRunAuditService(repository=_SubstitutingRepository(substituted=substituted))

    with pytest.raises(RuntimeError, match="substituted newly stored record"):
        service.store(record=record)


def test_blank_lookup_reference_is_rejected() -> None:
    service = NIIRunAuditService(repository=_MemoryRepository())

    with pytest.raises(ValueError, match="run_reference is required"):
        service.get(run_reference=" ")
