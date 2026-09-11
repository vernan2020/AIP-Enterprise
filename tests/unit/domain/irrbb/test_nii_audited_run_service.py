from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    RateType,
)
from aip.domain.irrbb.nii import (
    NIIAccrualType,
    NIIBalanceSheetAssumption,
    NIIInterestAccrual,
    NIIProjectionBasis,
    NIIShockTiming,
)
from aip.domain.irrbb.nii_projection import (
    NIIPositionProjection,
    NIIPositionProjectionStatus,
)
from aip.domain.irrbb.nii_readiness import (
    NIIProjectionCapabilityEvidence,
    NIIProjectionRequirementProfile,
    NIIProjectionScopeStatus,
)
from aip.domain.irrbb.nii_run_audit import (
    NIIRunAuditConflictError,
    NIIRunAuditRecord,
    NIIRunAuditRepositoryPutResult,
    NIIRunAuditWriteStatus,
)
from aip.domain.irrbb.nii_run_specification import NIIMethodologyRunSpecification
from aip.domain.irrbb.services.nii_audited_run_service import NIIAuditedRunService
from aip.shared.money import Currency, Money


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


def _specification(*, basis_source_reference: str = "basis:approved:v1") -> NIIMethodologyRunSpecification:
    return NIIMethodologyRunSpecification(
        run_reference="nii-run:2026-09-11:phase29",
        basis=_basis(source_reference=basis_source_reference),
        reporting_currency=Currency.CRC,
        stressed_scenarios=(IRRBBScenario.PARALLEL_UP, IRRBBScenario.PARALLEL_DOWN),
        policy_references=("policy:nii-methodology:v1", "policy:scenario-set:v1"),
        evidence_references=("evidence:portfolio-cutoff:2026-09-11",),
    )


def _position() -> BankingBookPosition:
    return BankingBookPosition(
        position_id="p1",
        product_type="TEST",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2027, 6, 30),
        source_reference="source:p1",
        contractual_rate=Decimal("0.05"),
    )


class _ProfileProvider:
    def profile_for(self, *, position: BankingBookPosition) -> NIIProjectionRequirementProfile:
        return NIIProjectionRequirementProfile(
            strategy_reference=f"strategy:{position.position_id}",
            source_reference=f"policy:strategy:{position.position_id}",
            scope_status=NIIProjectionScopeStatus.INCLUDED,
            requirements=(),
        )


class _CapabilityProvider:
    def evidence_for(
        self,
        *,
        position: BankingBookPosition,
        profile: NIIProjectionRequirementProfile,
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
    ) -> tuple[NIIProjectionCapabilityEvidence, ...]:
        return ()


class _Strategy:
    _amounts = {
        IRRBBScenario.BASE: Decimal("100"),
        IRRBBScenario.PARALLEL_UP: Decimal("80"),
        IRRBBScenario.PARALLEL_DOWN: Decimal("110"),
    }

    def project(
        self,
        *,
        position: BankingBookPosition,
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
    ) -> NIIPositionProjection:
        accrual = NIIInterestAccrual(
            accrual_id=f"{position.position_id}:{scenario.value}:1",
            position_id=position.position_id,
            scenario=scenario,
            accrual_type=NIIAccrualType.INTEREST_INCOME,
            amount=Money(self._amounts[scenario], Currency.CRC),
            accrual_start_date=basis.valuation_date,
            accrual_end_date=date(2026, 10, 11),
            source_reference=f"projection:{position.position_id}:{scenario.value}",
        )
        return NIIPositionProjection(
            position_id=position.position_id,
            scenario=scenario,
            basis=basis,
            strategy_reference=f"strategy:{position.position_id}",
            status=NIIPositionProjectionStatus.PROJECTED,
            accruals=(accrual,),
        )


class _CountingResolver:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def resolve(self, *, position: BankingBookPosition) -> _Strategy:
        self.calls += 1
        if self.fail:
            raise RuntimeError("projection strategy unavailable")
        return _Strategy()


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


def _execute(
    *,
    service: NIIAuditedRunService,
    specification: NIIMethodologyRunSpecification,
    resolver: _CountingResolver,
):
    return service.execute(
        positions=(_position(),),
        specification=specification,
        profile_provider=_ProfileProvider(),
        capability_provider=_CapabilityProvider(),
        strategy_resolver=resolver,
    )


def test_new_run_executes_and_persists_complete_audit_record() -> None:
    repository = _MemoryRepository()
    service = NIIAuditedRunService(repository=repository)
    specification = _specification()
    resolver = _CountingResolver()

    outcome = _execute(service=service, specification=specification, resolver=resolver)

    assert outcome.status is NIIRunAuditWriteStatus.STORED
    assert outcome.record.specification is specification
    assert outcome.record.result.specification is specification
    assert outcome.record.manifest.run_reference == specification.run_reference
    assert repository.records[specification.run_reference] == outcome.record
    assert resolver.calls == 3


def test_replay_of_same_run_returns_persisted_record_without_recalculation() -> None:
    repository = _MemoryRepository()
    service = NIIAuditedRunService(repository=repository)
    specification = _specification()
    first_resolver = _CountingResolver()
    first = _execute(service=service, specification=specification, resolver=first_resolver)
    replay_resolver = _CountingResolver(fail=True)

    replay = _execute(service=service, specification=specification, resolver=replay_resolver)

    assert replay.status is NIIRunAuditWriteStatus.IDEMPOTENT
    assert replay.record == first.record
    assert replay_resolver.calls == 0


def test_existing_run_with_different_specification_conflicts_before_recalculation() -> None:
    repository = _MemoryRepository()
    service = NIIAuditedRunService(repository=repository)
    _execute(service=service, specification=_specification(), resolver=_CountingResolver())
    changed = _specification(basis_source_reference="basis:approved:v2")
    resolver = _CountingResolver(fail=True)

    with pytest.raises(NIIRunAuditConflictError, match="different methodology run specification"):
        _execute(service=service, specification=changed, resolver=resolver)

    assert resolver.calls == 0


def test_execution_failure_does_not_create_partial_audit_record() -> None:
    repository = _MemoryRepository()
    service = NIIAuditedRunService(repository=repository)
    resolver = _CountingResolver(fail=True)

    with pytest.raises(RuntimeError, match="projection strategy unavailable"):
        _execute(service=service, specification=_specification(), resolver=resolver)

    assert repository.records == {}
