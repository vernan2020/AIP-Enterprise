from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowDirection,
    IRRBBCashFlow,
    IRRBBInstrumentClass,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.services.scenario_evaluation_service import (
    IRRBBScenarioEvaluationService,
)
from aip.shared.money import Currency, Money

_VALUATION_DATE = date(2026, 8, 31)
_CRC = Currency.CRC


class _UnitDiscountFactors:
    def discount_factor(
        self,
        *,
        currency: Currency,
        scenario: IRRBBScenario,
        valuation_date: date,
        payment_date: date,
    ) -> Decimal:
        del currency, scenario, valuation_date, payment_date
        return Decimal("1")


class _ScenarioFlows:
    _AMOUNTS = {
        IRRBBScenario.BASE: Decimal("1000"),
        IRRBBScenario.PARALLEL_UP: Decimal("800"),
        IRRBBScenario.PARALLEL_DOWN: Decimal("1100"),
        IRRBBScenario.STEEPENER: Decimal("950"),
        IRRBBScenario.FLATTENER: Decimal("900"),
        IRRBBScenario.SHORT_UP: Decimal("700"),
        IRRBBScenario.SHORT_DOWN: Decimal("1050"),
    }

    def cashflows_for(
        self,
        *,
        position: BankingBookPosition,
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        del valuation_date
        return (
            IRRBBCashFlow(
                position_id=position.position_id,
                side=position.side,
                direction=CashFlowDirection.RECEIVABLE,
                amount=Money(self._AMOUNTS[scenario], position.currency),
                cashflow_date=date(2027, 8, 31),
                risk_date=date(2027, 8, 31),
                flow_type="PRINCIPAL",
                source_reference=f"TEST:{position.position_id}:{scenario.value}",
            ),
        )


class _WrongPositionFlows:
    def cashflows_for(
        self,
        *,
        position: BankingBookPosition,
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        del scenario, valuation_date
        return (
            IRRBBCashFlow(
                position_id=f"OTHER-{position.position_id}",
                side=position.side,
                direction=CashFlowDirection.RECEIVABLE,
                amount=Money(Decimal("100"), position.currency),
                cashflow_date=date(2027, 8, 31),
                risk_date=date(2027, 8, 31),
                flow_type="PRINCIPAL",
                source_reference="TEST:WRONG",
            ),
        )


def _position(position_id: str = "ASSET-1") -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type="FIXED_ASSET",
        side=BankingBookSide.ASSET,
        currency=_CRC,
        principal=Money(Decimal("1000"), _CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2027, 8, 31),
        source_reference=f"TEST:{position_id}",
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.BULLET,
    )


def _methodology() -> IRRBBMethodologyProfile:
    return IRRBBMethodologyProfile(
        code="IRRBB_TEST",
        version="1",
        status=IRRBBMethodologyStatus.INTERNAL,
        source_reference="TEST_METHODOLOGY",
    )


def test_evaluate_runs_base_and_all_six_stresses_and_identifies_worst_loss() -> None:
    service = IRRBBScenarioEvaluationService(
        scenario_cashflows=_ScenarioFlows(),
        discount_factors=_UnitDiscountFactors(),
    )

    result = service.evaluate(
        positions=(_position(),),
        valuation_date=_VALUATION_DATE,
        reporting_currency=_CRC,
        tier_one_capital=Money(Decimal("2000"), _CRC),
        methodology=_methodology(),
    )

    assert result.base.eve == Money(Decimal("1000"), _CRC)
    assert len(result.stressed) == 6
    assert result.exposure.worst_scenario is IRRBBScenario.SHORT_UP
    assert result.exposure.worst_loss == Money(Decimal("300"), _CRC)
    assert result.exposure.exposure_ratio_to_tier1 == Decimal("0.15")
    assert result.methodology.code == "IRRBB_TEST"
    assert result.position_count == 1


def test_evaluate_rejects_duplicate_position_ids() -> None:
    service = IRRBBScenarioEvaluationService(
        scenario_cashflows=_ScenarioFlows(),
        discount_factors=_UnitDiscountFactors(),
    )

    with pytest.raises(ValueError, match="position_id values must be unique"):
        service.evaluate(
            positions=(_position("DUP"), _position("DUP")),
            valuation_date=_VALUATION_DATE,
            reporting_currency=_CRC,
            tier_one_capital=Money(Decimal("2000"), _CRC),
            methodology=_methodology(),
        )


def test_evaluate_rejects_empty_position_set() -> None:
    service = IRRBBScenarioEvaluationService(
        scenario_cashflows=_ScenarioFlows(),
        discount_factors=_UnitDiscountFactors(),
    )

    with pytest.raises(ValueError, match="at least one position"):
        service.evaluate(
            positions=(),
            valuation_date=_VALUATION_DATE,
            reporting_currency=_CRC,
            tier_one_capital=Money(Decimal("2000"), _CRC),
            methodology=_methodology(),
        )


def test_evaluate_rejects_cash_flow_for_different_position() -> None:
    service = IRRBBScenarioEvaluationService(
        scenario_cashflows=_WrongPositionFlows(),
        discount_factors=_UnitDiscountFactors(),
    )

    with pytest.raises(ValueError, match="different position"):
        service.evaluate(
            positions=(_position(),),
            valuation_date=_VALUATION_DATE,
            reporting_currency=_CRC,
            tier_one_capital=Money(Decimal("2000"), _CRC),
            methodology=_methodology(),
        )


def test_evaluate_rejects_base_inside_required_stress_scenarios() -> None:
    service = IRRBBScenarioEvaluationService(
        scenario_cashflows=_ScenarioFlows(),
        discount_factors=_UnitDiscountFactors(),
    )

    with pytest.raises(ValueError, match="cannot contain BASE"):
        service.evaluate(
            positions=(_position(),),
            valuation_date=_VALUATION_DATE,
            reporting_currency=_CRC,
            tier_one_capital=Money(Decimal("2000"), _CRC),
            methodology=_methodology(),
            required_scenarios=(IRRBBScenario.BASE,),
        )
