from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from threading import Lock

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
from aip.domain.irrbb.nii_audit_repository_conformance import (
    NIIAuditRepositoryConformanceCheck,
    NIIAuditRepositoryConformanceFixture,
    NIIAuditRepositoryConformanceSuite,
)
from aip.domain.irrbb.nii_run_audit import (
    NIIRunAuditRecord,
    NIIRunAuditRepositoryIntegrityError,
    NIIRunAuditRepositoryPutResult,
)
from aip.domain.irrbb.nii_run_specification import (
    NIIMethodologyRunResult,
    NIIMethodologyRunSpecification,
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


def _record(
    *,
    run_reference: str,
    basis_source_reference: str = "basis:approved:v1",
    result_marker: str = "result:v1",
) -> NIIRunAuditRecord:
    specification = NIIMethodologyRunSpecification(
        run_reference=run_reference,
        basis=_basis(source_reference=basis_source_reference),
        reporting_currency=Currency.CRC,
        stressed_scenarios=(IRRBBScenario.PARALLEL_UP, IRRBBScenario.PARALLEL_DOWN),
        policy_references=("policy:nii-methodology:v1", "policy:scenario-set:v1"),
        evidence_references=("evidence:portfolio-cutoff:2026-09-11",),
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


def _fixture() -> NIIAuditRepositoryConformanceFixture:
    return NIIAuditRepositoryConformanceFixture(
        primary=_record(run_reference="nii-run:phase31:primary"),
        conflicting=_record(
            run_reference="nii-run:phase31:primary",
            basis_source_reference="basis:approved:v2",
        ),
        secondary=_record(run_reference="nii-run:phase31:secondary"),
    )


class _BackingStore:
    def __init__(self) -> None:
        self.records: dict[str, NIIRunAuditRecord] = {}
        self.corrupted: set[str] = set()
        self.lock = Lock()


class _ConformantMemoryRepository:
    def __init__(self, *, store: _BackingStore) -> None:
        self._store = store

    def get_by_run_reference(self, *, run_reference: str) -> NIIRunAuditRecord | None:
        with self._store.lock:
            if run_reference in self._store.corrupted:
                raise NIIRunAuditRepositoryIntegrityError(
                    f"Integrity verification failed for {run_reference}"
                )
            return self._store.records.get(run_reference)

    def put_if_absent(self, *, record: NIIRunAuditRecord) -> NIIRunAuditRepositoryPutResult:
        with self._store.lock:
            existing = self._store.records.get(record.run_reference)
            if existing is not None:
                return NIIRunAuditRepositoryPutResult(created=False, record=existing)
            self._store.records[record.run_reference] = record
            return NIIRunAuditRepositoryPutResult(created=True, record=record)


class _ConformantHarness:
    def __init__(self) -> None:
        self._store = _BackingStore()

    def reset(self) -> None:
        self._store = _BackingStore()

    def repository(self) -> _ConformantMemoryRepository:
        return _ConformantMemoryRepository(store=self._store)

    def reopen_repository(self) -> _ConformantMemoryRepository:
        return _ConformantMemoryRepository(store=self._store)

    def corrupt_persisted_record(self, *, run_reference: str) -> None:
        with self._store.lock:
            if run_reference not in self._store.records:
                raise AssertionError("Cannot corrupt a record that was not persisted")
            self._store.corrupted.add(run_reference)


class _NonIdempotentRepository(_ConformantMemoryRepository):
    def put_if_absent(self, *, record: NIIRunAuditRecord) -> NIIRunAuditRepositoryPutResult:
        with self._store.lock:
            self._store.records[record.run_reference] = record
            return NIIRunAuditRepositoryPutResult(created=True, record=record)


class _NonIdempotentHarness(_ConformantHarness):
    def repository(self) -> _NonIdempotentRepository:
        return _NonIdempotentRepository(store=self._store)

    def reopen_repository(self) -> _NonIdempotentRepository:
        return _NonIdempotentRepository(store=self._store)


def test_conformant_repository_passes_every_executable_check() -> None:
    result = NIIAuditRepositoryConformanceSuite.run(
        adapter_reference="test:memory-conformant:v1",
        harness=_ConformantHarness(),
        fixture=_fixture(),
    )

    assert result.is_conformant is True
    assert result.failures == ()
    assert result.passed == frozenset(NIIAuditRepositoryConformanceCheck)


def test_non_idempotent_repository_reports_exact_failed_behaviors() -> None:
    result = NIIAuditRepositoryConformanceSuite.run(
        adapter_reference="test:memory-non-idempotent:v1",
        harness=_NonIdempotentHarness(),
        fixture=_fixture(),
    )

    failed = {failure.check for failure in result.failures}
    assert result.is_conformant is False
    assert NIIAuditRepositoryConformanceCheck.IDEMPOTENT_REPEAT in failed
    assert NIIAuditRepositoryConformanceCheck.UNIQUE_RUN_REFERENCE in failed
    assert NIIAuditRepositoryConformanceCheck.ATOMIC_CONCURRENT_PUT_IF_ABSENT in failed


def test_fixture_rejects_conflict_with_different_run_reference() -> None:
    primary = _record(run_reference="nii-run:phase31:primary")
    secondary = _record(run_reference="nii-run:phase31:secondary")

    try:
        NIIAuditRepositoryConformanceFixture(
            primary=primary,
            conflicting=secondary,
            secondary=_record(run_reference="nii-run:phase31:third"),
        )
    except ValueError as exc:
        assert "reuse the primary run_reference" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected invalid conformance fixture to fail closed")


def test_blank_adapter_reference_is_rejected() -> None:
    try:
        NIIAuditRepositoryConformanceSuite.run(
            adapter_reference=" ",
            harness=_ConformantHarness(),
            fixture=_fixture(),
        )
    except ValueError as exc:
        assert "adapter_reference is required" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected blank adapter reference to fail closed")
