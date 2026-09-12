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
from aip.domain.irrbb.nii_run_specification import NIIMethodologyRunSpecification
from aip.domain.irrbb.nii_scenario_set import NIIScenarioSetEvaluationStatus
from aip.domain.irrbb.services.nii_methodology_run_service import NIIMethodologyRunService
from aip.shared.money import Currency, Money


def _basis() -> NIIProjectionBasis:
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
        source_reference="basis:approved:2026-09-11",
    )


def _specification() -> NIIMethodologyRunSpecification:
    return NIIMethodologyRunSpecification(
        run_reference="nii-run:2026-09-11:001",
        basis=_basis(),
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
        assert position.position_id == "p1"
        return NIIProjectionRequirementProfile(
            strategy_reference="strategy:p1",
            source_reference="policy:strategy:p1",
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
        assert position.position_id == "p1"
        assert profile.strategy_reference == "strategy:p1"
        assert basis == _basis()
        assert scenario in (
            IRRBBScenario.BASE,
            IRRBBScenario.PARALLEL_UP,
            IRRBBScenario.PARALLEL_DOWN,
        )
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
            strategy_reference="strategy:p1",
            status=NIIPositionProjectionStatus.PROJECTED,
            accruals=(accrual,),
        )


class _Resolver:
    def resolve(self, *, position: BankingBookPosition) -> _Strategy:
        assert position.position_id == "p1"
        return _Strategy()


def test_executes_exact_specification_and_binds_result_to_it() -> None:
    specification = _specification()

    result = NIIMethodologyRunService.execute(
        positions=(_position(),),
        specification=specification,
        profile_provider=_ProfileProvider(),
        capability_provider=_CapabilityProvider(),
        strategy_resolver=_Resolver(),
    )

    assert result.specification is specification
    assert result.evaluation.status is NIIScenarioSetEvaluationStatus.EVALUATED
    assert result.evaluation.basis == specification.basis
    assert result.evaluation.reporting_currency is specification.reporting_currency
    assert result.evaluation.required_stressed_scenarios == specification.stressed_scenarios
    assert result.evaluation.delta_nii is not None
    assert result.evaluation.delta_nii.worst_scenario is IRRBBScenario.PARALLEL_UP
    assert result.evaluation.delta_nii.worst_loss.amount == Decimal("20")


@pytest.mark.parametrize(
    ("stressed_scenarios", "message"),
    [
        ((), "requires stressed scenarios"),
        ((IRRBBScenario.BASE,), "cannot include BASE"),
        (
            (IRRBBScenario.PARALLEL_UP, IRRBBScenario.PARALLEL_UP),
            "cannot contain duplicates",
        ),
    ],
)
def test_specification_rejects_ambiguous_scenario_sets(
    stressed_scenarios: tuple[IRRBBScenario, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        NIIMethodologyRunSpecification(
            run_reference="nii-run:test",
            basis=_basis(),
            reporting_currency=Currency.CRC,
            stressed_scenarios=stressed_scenarios,
            policy_references=("policy:nii",),
            evidence_references=("evidence:cutoff",),
        )


@pytest.mark.parametrize(
    ("policy_references", "evidence_references", "message"),
    [
        ((), ("evidence:cutoff",), "requires policy references"),
        (("policy:nii",), (), "requires evidence references"),
        ((" ",), ("evidence:cutoff",), "policy references cannot be blank"),
        (("policy:nii",), ("",), "evidence references cannot be blank"),
        (
            ("policy:nii", "policy:nii"),
            ("evidence:cutoff",),
            "policy references cannot contain duplicates",
        ),
    ],
)
def test_specification_requires_explicit_unique_governance_references(
    policy_references: tuple[str, ...],
    evidence_references: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        NIIMethodologyRunSpecification(
            run_reference="nii-run:test",
            basis=_basis(),
            reporting_currency=Currency.CRC,
            stressed_scenarios=(IRRBBScenario.PARALLEL_UP,),
            policy_references=policy_references,
            evidence_references=evidence_references,
        )


def test_specification_requires_nonblank_run_reference() -> None:
    with pytest.raises(ValueError, match="run_reference is required"):
        NIIMethodologyRunSpecification(
            run_reference=" ",
            basis=_basis(),
            reporting_currency=Currency.CRC,
            stressed_scenarios=(IRRBBScenario.PARALLEL_UP,),
            policy_references=("policy:nii",),
            evidence_references=("evidence:cutoff",),
        )
