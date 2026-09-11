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
    NIIProjectionEvidenceAlternative,
    NIIProjectionEvidenceKey,
    NIIProjectionRequirement,
    NIIProjectionRequirementProfile,
    NIIProjectionScopeStatus,
)
from aip.domain.irrbb.nii_scenario_set import NIIScenarioSetEvaluationStatus
from aip.domain.irrbb.services.nii_scenario_set_evaluation_service import (
    NIIScenarioSetEvaluationService,
)
from aip.shared.money import Currency, Money


def _basis() -> NIIProjectionBasis:
    return NIIProjectionBasis(
        methodology=IRRBBMethodologyProfile(
            code="INTERNAL-NII",
            version="2026.09.11",
            status=IRRBBMethodologyStatus.INTERNAL,
            source_reference="policy:nii",
        ),
        valuation_date=date(2026, 9, 11),
        horizon_end_date=date(2027, 9, 11),
        balance_sheet_assumption=NIIBalanceSheetAssumption.CONSTANT,
        shock_timing=NIIShockTiming.INSTANTANEOUS,
        source_reference="projection:approved-input",
    )


def _position(position_id: str = "p1") -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type="TEST",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2027, 6, 30),
        source_reference=f"source:{position_id}",
        contractual_rate=Decimal("0.05"),
    )


def _requirement(key: NIIProjectionEvidenceKey) -> NIIProjectionRequirement:
    return NIIProjectionRequirement(
        requirement_id=f"require-{key.value.lower()}",
        alternatives=(NIIProjectionEvidenceAlternative(keys=frozenset({key})),),
        message=f"{key.value} is required.",
    )


def _included_profile(
    strategy_reference: str = "strategy:p1",
    *requirements: NIIProjectionRequirement,
) -> NIIProjectionRequirementProfile:
    return NIIProjectionRequirementProfile(
        strategy_reference=strategy_reference,
        source_reference=f"policy:{strategy_reference}",
        scope_status=NIIProjectionScopeStatus.INCLUDED,
        requirements=tuple(requirements),
    )


def _excluded_profile(strategy_reference: str = "strategy:p1") -> NIIProjectionRequirementProfile:
    return NIIProjectionRequirementProfile(
        strategy_reference=strategy_reference,
        source_reference=f"policy:{strategy_reference}",
        scope_status=NIIProjectionScopeStatus.EXCLUDED,
        exclusion_reason="Outside approved NII perimeter.",
    )


class _ProfileProvider:
    def __init__(self, profile: NIIProjectionRequirementProfile) -> None:
        self._profile = profile

    def profile_for(self, *, position: BankingBookPosition) -> NIIProjectionRequirementProfile:
        assert position.position_id == "p1"
        return self._profile


class _CapabilityProvider:
    def __init__(
        self,
        by_scenario: dict[IRRBBScenario, tuple[NIIProjectionCapabilityEvidence, ...]] | None = None,
    ) -> None:
        self._by_scenario = by_scenario or {}
        self.calls: list[IRRBBScenario] = []

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
        self.calls.append(scenario)
        return self._by_scenario.get(scenario, ())


class _Strategy:
    def __init__(self, amounts: dict[IRRBBScenario, Decimal]) -> None:
        self._amounts = amounts
        self.calls: list[IRRBBScenario] = []

    def project(
        self,
        *,
        position: BankingBookPosition,
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
    ) -> NIIPositionProjection:
        self.calls.append(scenario)
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


class _NoAccrualStrategy:
    def project(
        self,
        *,
        position: BankingBookPosition,
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
    ) -> NIIPositionProjection:
        return NIIPositionProjection(
            position_id=position.position_id,
            scenario=scenario,
            basis=basis,
            strategy_reference="strategy:p1",
            status=NIIPositionProjectionStatus.NO_ACCRUAL_IN_HORIZON,
            accruals=(),
        )


class _Resolver:
    def __init__(self, strategy: _Strategy | _NoAccrualStrategy) -> None:
        self._strategy = strategy
        self.calls: list[str] = []

    def resolve(self, *, position: BankingBookPosition) -> _Strategy | _NoAccrualStrategy:
        self.calls.append(position.position_id)
        return self._strategy


def test_evaluates_base_and_explicit_stresses_and_calculates_delta_nii() -> None:
    amounts = {
        IRRBBScenario.BASE: Decimal("100"),
        IRRBBScenario.PARALLEL_UP: Decimal("80"),
        IRRBBScenario.PARALLEL_DOWN: Decimal("110"),
    }
    strategy = _Strategy(amounts)

    result = NIIScenarioSetEvaluationService.evaluate(
        positions=(_position(),),
        basis=_basis(),
        stressed_scenarios=(IRRBBScenario.PARALLEL_UP, IRRBBScenario.PARALLEL_DOWN),
        reporting_currency=Currency.CRC,
        profile_provider=_ProfileProvider(_included_profile()),
        capability_provider=_CapabilityProvider(),
        strategy_resolver=_Resolver(strategy),
    )

    assert result.status is NIIScenarioSetEvaluationStatus.EVALUATED
    assert tuple(item.scenario for item in result.certifications) == (
        IRRBBScenario.BASE,
        IRRBBScenario.PARALLEL_UP,
        IRRBBScenario.PARALLEL_DOWN,
    )
    assert tuple(item.net_interest_income.amount for item in result.scenario_results) == (
        Decimal("100"),
        Decimal("80"),
        Decimal("110"),
    )
    assert result.delta_nii is not None
    assert result.delta_nii.worst_scenario is IRRBBScenario.PARALLEL_UP
    assert result.delta_nii.worst_loss.amount == Decimal("20")
    assert strategy.calls == [
        IRRBBScenario.BASE,
        IRRBBScenario.PARALLEL_UP,
        IRRBBScenario.PARALLEL_DOWN,
    ]


def test_any_blocked_scenario_blocks_scenario_set_before_nii_aggregation() -> None:
    key = NIIProjectionEvidenceKey.FORWARD_REFERENCE_RATE_CURVE
    evidence = NIIProjectionCapabilityEvidence(
        key=key,
        source_reference="curve:approved:v1",
    )
    capability_provider = _CapabilityProvider(
        {
            IRRBBScenario.BASE: (evidence,),
            IRRBBScenario.PARALLEL_UP: (evidence,),
            IRRBBScenario.PARALLEL_DOWN: (),
        }
    )
    strategy = _Strategy(
        {
            IRRBBScenario.BASE: Decimal("100"),
            IRRBBScenario.PARALLEL_UP: Decimal("90"),
        }
    )

    result = NIIScenarioSetEvaluationService.evaluate(
        positions=(_position(),),
        basis=_basis(),
        stressed_scenarios=(IRRBBScenario.PARALLEL_UP, IRRBBScenario.PARALLEL_DOWN),
        reporting_currency=Currency.CRC,
        profile_provider=_ProfileProvider(_included_profile("strategy:p1", _requirement(key))),
        capability_provider=capability_provider,
        strategy_resolver=_Resolver(strategy),
    )

    assert result.status is NIIScenarioSetEvaluationStatus.BLOCKED
    assert result.scenario_results == ()
    assert result.delta_nii is None
    assert strategy.calls == [IRRBBScenario.BASE, IRRBBScenario.PARALLEL_UP]


def test_excluded_only_portfolio_is_explicit_and_does_not_resolve_strategy() -> None:
    resolver = _Resolver(_NoAccrualStrategy())
    capability_provider = _CapabilityProvider()

    result = NIIScenarioSetEvaluationService.evaluate(
        positions=(_position(),),
        basis=_basis(),
        stressed_scenarios=(IRRBBScenario.PARALLEL_UP,),
        reporting_currency=Currency.CRC,
        profile_provider=_ProfileProvider(_excluded_profile()),
        capability_provider=capability_provider,
        strategy_resolver=resolver,
    )

    assert result.status is NIIScenarioSetEvaluationStatus.NO_INCLUDED_POSITIONS
    assert result.scenario_results == ()
    assert result.delta_nii is None
    assert capability_provider.calls == []
    assert resolver.calls == []


def test_projected_scenario_without_accruals_does_not_silently_become_zero_nii() -> None:
    with pytest.raises(ValueError, match="zero-NII policy is not defined"):
        NIIScenarioSetEvaluationService.evaluate(
            positions=(_position(),),
            basis=_basis(),
            stressed_scenarios=(IRRBBScenario.PARALLEL_UP,),
            reporting_currency=Currency.CRC,
            profile_provider=_ProfileProvider(_included_profile()),
            capability_provider=_CapabilityProvider(),
            strategy_resolver=_Resolver(_NoAccrualStrategy()),
        )


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
def test_rejects_ambiguous_or_invalid_scenario_sets(
    stressed_scenarios: tuple[IRRBBScenario, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        NIIScenarioSetEvaluationService.evaluate(
            positions=(_position(),),
            basis=_basis(),
            stressed_scenarios=stressed_scenarios,
            reporting_currency=Currency.CRC,
            profile_provider=_ProfileProvider(_included_profile()),
            capability_provider=_CapabilityProvider(),
            strategy_resolver=_Resolver(_NoAccrualStrategy()),
        )
