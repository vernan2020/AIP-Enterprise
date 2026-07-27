from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.financial_math import (
    BootstrapError,
    CashFlow,
    CashFlowSeries,
    ConvergenceError,
    CurveConstructionError,
    CurrencyMismatchError,
    EffectiveRate,
    ForwardRate,
    InterestRate,
    InterpolationError,
    InvalidBracketError,
    InvalidCashFlowError,
    InvalidRateError,
    NominalRate,
    ZeroRate,
    accumulation_factor,
    accrue_interest,
    bisection_solve,
    brent_solve,
    bootstrap_zero_curve,
    clean_price,
    convexity,
    discount_factor,
    dirty_price,
    dv01,
    effective_duration,
    equivalent_rate,
    future_value,
    future_value_series,
    interpolate_linear,
    interpolate_logarithmic,
    internal_rate_of_return,
    macaulay_duration,
    modified_duration,
    money_weighted_return,
    nelson_siegel_curve,
    nelson_siegel_zero_rate,
    newton_raphson_solve,
    present_value,
    present_value_series,
    pvbp,
    svensson_curve,
    svensson_zero_rate,
    yield_to_maturity,
)
from aip.domain.financial_math.bond_metrics.accrued_interest import accrued_interest as accrued_interest_fn
from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.financial_math.root_finding.bisection import ConvergenceResult


def test_cash_flow_and_series_behaviour() -> None:
    flow = CashFlow(payment_date=date(2025, 1, 1), amount=Decimal("100"), currency="USD")
    assert flow.amount == Decimal("100")

    series = CashFlowSeries.from_cashflows([flow, CashFlow(date(2024, 1, 1), Decimal("50"), "USD")])
    assert series.order_chronologically()[0].payment_date == date(2024, 1, 1)
    assert series.total_amount() == Decimal("150")
    filtered = series.filter_by_date_range(date(2024, 1, 1), date(2024, 12, 31))
    assert len(filtered.cash_flows) == 1

    with pytest.raises(CurrencyMismatchError):
        CashFlowSeries(cash_flows=(flow, CashFlow(date(2025, 2, 1), Decimal("20"), "EUR")))


def test_cash_flow_series_duplicate_aggregation_with_fx() -> None:
    series = CashFlowSeries.from_cashflows(
        [CashFlow(date(2024, 1, 1), Decimal("100"), "USD"), CashFlow(date(2024, 1, 1), Decimal("25"), "USD")]
    )
    aggregated = series.aggregate_duplicates()
    assert aggregated.total_amount() == Decimal("125")

    mixed = CashFlowSeries.from_cashflows(
        [CashFlow(date(2024, 1, 1), Decimal("100"), "USD"), CashFlow(date(2024, 1, 1), Decimal("25"), "EUR")]
    )
    with pytest.raises(CurrencyMismatchError):
        mixed.aggregate_duplicates()

    with pytest.raises(InvalidCashFlowError):
        CashFlow(payment_date=date(2024, 1, 1), amount=Decimal("0"), currency="USD")


def test_compounding_and_rate_conversion() -> None:
    assert accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="annual") == Decimal("1.05")
    assert discount_factor(Decimal("0.05"), Decimal("1"), compounding="annual") == Decimal("0.9523809523809523809523809524")
    assert equivalent_rate(Decimal("0.05"), from_compounding="annual", to_compounding="semiannual") > Decimal("0")
    with pytest.raises(InvalidRateError):
        accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="bad")


def test_present_and_future_value_with_interest_rate_object() -> None:
    rate = InterestRate(rate=Decimal("0.05"), compounding="annual", frequency=1)
    flow = CashFlow(payment_date=date(2025, 1, 1), amount=Decimal("100"), currency="USD")
    valuation_date = date(2024, 1, 1)
    assert present_value(flow, rate, valuation_date=valuation_date) < Decimal("100")
    assert future_value(flow, rate, valuation_date=valuation_date) > Decimal("100")

    series = CashFlowSeries.from_cashflows([flow, CashFlow(date(2026, 1, 1), Decimal("100"), "USD")])
    assert present_value_series(series, rate, valuation_date=valuation_date) > Decimal("0")
    assert future_value_series(series, rate, valuation_date=valuation_date) > Decimal("0")


def test_rate_value_objects_capture_compounding_metadata() -> None:
    effective = EffectiveRate(rate=Decimal("0.06"))
    nominal = NominalRate(rate=Decimal("0.06"), compounding="semiannual", frequency=2)
    zero = ZeroRate(rate=Decimal("-0.01"), maturity=Decimal("1"))
    forward = ForwardRate(rate=Decimal("0.02"), start_tenor=Decimal("1"), end_tenor=Decimal("2"))

    assert effective.compounding == "annual"
    assert nominal.frequency == 2
    assert zero.rate < Decimal("0")
    assert forward.start_tenor == Decimal("1")


def test_root_finding_convergence_and_errors() -> None:
    result = bisection_solve(lambda x: x * x - Decimal("4"), Decimal("0"), Decimal("3"), tolerance=Decimal("1e-8"))
    assert result.converged and result.root == pytest.approx(2, abs=1e-6)

    with pytest.raises(InvalidBracketError):
        bisection_solve(lambda x: x * x - Decimal("4"), Decimal("0"), Decimal("1"))

    with pytest.raises(ConvergenceError):
        newton_raphson_solve(lambda x: x * x + Decimal("1"), lambda x: Decimal("2") * x, Decimal("1"), tolerance=Decimal("1e-8"))

    with pytest.raises(InvalidBracketError):
        brent_solve(lambda x: x * x - Decimal("4"), Decimal("0"), Decimal("1"), tolerance=Decimal("1e-8"))


def test_yield_and_irr_converge_for_known_cash_flows() -> None:
    cash_flows = [CashFlow(date(2024, 1, 1), Decimal("-100"), "USD"), CashFlow(date(2025, 1, 1), Decimal("110"), "USD")]
    summary = yield_to_maturity(cash_flows, Decimal("100"), settlement_date=date(2024, 1, 1))
    assert summary.converged
    irr = internal_rate_of_return(cash_flows, settlement_date=date(2024, 1, 1))
    assert irr > Decimal("0")
    assert money_weighted_return(cash_flows, settlement_date=date(2024, 1, 1)) > Decimal("0")


def test_interpolation_and_curve_behaviour() -> None:
    assert interpolate_linear([Decimal("0"), Decimal("2")], [Decimal("0"), Decimal("4")], Decimal("1")) == Decimal("2")
    assert interpolate_logarithmic([Decimal("1"), Decimal("2")], [Decimal("1"), Decimal("4")], Decimal("1.5")) > Decimal("1")

    with pytest.raises(InterpolationError):
        interpolate_linear([Decimal("0"), Decimal("2")], [Decimal("1"), Decimal("3")], Decimal("3"))

    with pytest.raises(InterpolationError):
        interpolate_logarithmic([Decimal("0"), Decimal("2")], [Decimal("1"), Decimal("3")], Decimal("3"))

    curve = YieldCurve(
        valuation_date=date(2024, 1, 1),
        currency="USD",
        points=(CurvePoint(Decimal("1"), Decimal("0.04")), CurvePoint(Decimal("2"), Decimal("0.05"))),
    )
    assert curve.zero_rate(Decimal("1")) == Decimal("0.04")
    assert curve.discount_factor(Decimal("1")) < Decimal("1")
    assert curve.forward_rate(Decimal("1"), Decimal("2")) > Decimal("0")

    with pytest.raises(CurveConstructionError):
        YieldCurve(valuation_date=date(2024, 1, 1), currency="USD", points=(CurvePoint(Decimal("1"), Decimal("0.01")), CurvePoint(Decimal("1"), Decimal("0.02"))))


def test_bootstrap_and_curves() -> None:
    result = bootstrap_zero_curve([(Decimal("1"), Decimal("95"), Decimal("100"))], tolerance=Decimal("0.1"))
    assert result.points[0].tenor == Decimal("1")
    assert len(result.residuals) == 1

    assert nelson_siegel_zero_rate(Decimal("0"), beta0=Decimal("0.01"), beta1=Decimal("0.02"), beta2=Decimal("0.03"), tau=Decimal("1")) == Decimal("0.01")
    assert svensson_zero_rate(Decimal("0"), beta0=Decimal("0.01"), beta1=Decimal("0.02"), beta2=Decimal("0.03"), beta3=Decimal("0.04"), tau1=Decimal("1"), tau2=Decimal("2")) == Decimal("0.01")
    assert len(nelson_siegel_curve([Decimal("0"), Decimal("1")], beta0=Decimal("0.01"), beta1=Decimal("0.02"), beta2=Decimal("0.03"), tau=Decimal("1"))) == 2
    assert len(svensson_curve([Decimal("0"), Decimal("1")], beta0=Decimal("0.01"), beta1=Decimal("0.02"), beta2=Decimal("0.03"), beta3=Decimal("0.04"), tau1=Decimal("1"), tau2=Decimal("2"))) == 2


def test_bond_metrics_consistency_and_reference_behaviour() -> None:
    cash_flows = [(Decimal("1"), Decimal("100")), (Decimal("2"), Decimal("1100"))]
    assert accrued_interest_fn(Decimal("0.05"), Decimal("1000"), days_since_last_coupon=30, days_in_period=180) == Decimal("8.333333333333333333")

    assert dirty_price(Decimal("95"), Decimal("5")) == Decimal("100")
    assert clean_price(Decimal("100"), Decimal("5")) == Decimal("95")

    assert macaulay_duration(cash_flows, Decimal("0.05")) > Decimal("0")
    assert modified_duration(cash_flows, Decimal("0.05")) > Decimal("0")
    assert effective_duration(cash_flows, Decimal("0.05"), shock=Decimal("0.001")) > Decimal("0")
    assert convexity(cash_flows, Decimal("0.05")) > Decimal("0")
    assert dv01(cash_flows, Decimal("0.05"), shock=Decimal("0.0001")) > Decimal("0")
    assert pvbp(cash_flows, Decimal("0.05"), shock=Decimal("0.0001")) > Decimal("0")
