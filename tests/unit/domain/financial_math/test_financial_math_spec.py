from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.financial_math import (
    BootstrapError,
    CashFlow,
    CashFlowSeries,
    ConvergenceError,
    CurrencyMismatchError,
    CurveConstructionError,
    EffectiveRate,
    ForwardRate,
    InterestRate,
    InterpolationError,
    InvalidBracketError,
    InvalidCashFlowError,
    InvalidRateError,
    NominalRate,
    ZeroRate,
    accrued_interest,
    accumulation_factor,
    bisection_solve,
    bootstrap_zero_curve,
    brent_solve,
    clean_price,
    convexity,
    dirty_price,
    discount_factor,
    dv01,
    effective_duration,
    equivalent_rate,
    future_value,
    future_value_series,
    internal_rate_of_return,
    interpolate_linear,
    interpolate_logarithmic,
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
from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.financial_math.root_finding.bisection import ConvergenceResult


def _assert_close(left: Decimal, right: Decimal, *, tolerance: Decimal = Decimal("1e-6")) -> None:
    assert abs(left - right) <= tolerance


def test_cash_flow_validation_and_series_valuation() -> None:
    flow = CashFlow(payment_date=date(2025, 1, 1), amount=Decimal("100"), currency="USD")
    rate = InterestRate(rate=Decimal("0.05"), compounding="annual", frequency=1)

    assert present_value(flow, rate, valuation_date=date(2024, 1, 1)) < flow.amount
    assert future_value(flow, rate, valuation_date=date(2024, 1, 1)) > flow.amount

    series = CashFlowSeries.from_cashflows([flow, CashFlow(date(2026, 1, 1), Decimal("50"), "USD")])
    assert present_value_series(series, rate, valuation_date=date(2024, 1, 1)) > Decimal("0")
    assert future_value_series(series, rate, valuation_date=date(2024, 1, 1)) > Decimal("0")

    with pytest.raises(InvalidCashFlowError):
        CashFlow(payment_date=date(2025, 1, 1), amount=Decimal("0"), currency="USD")
    with pytest.raises(InvalidCashFlowError):
        CashFlowSeries(cash_flows=())
    with pytest.raises(CurrencyMismatchError):
        CashFlowSeries(cash_flows=(flow, CashFlow(date(2025, 2, 1), Decimal("20"), "EUR")))


def test_compounding_and_equivalent_rates_have_explicit_decimal_semantics() -> None:
    assert accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="annual") == Decimal(
        "1.05"
    )
    assert accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="simple") == Decimal(
        "1.05"
    )
    assert accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="semiannual") == Decimal(
        "1.050625"
    )
    assert accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="continuous") > Decimal(
        "1"
    )
    assert discount_factor(Decimal("0.05"), Decimal("1"), compounding="annual") == Decimal(
        "0.9523809523809523809523809524"
    )

    expected_semiannual = Decimal("0.04939015319192")
    assert (
        equivalent_rate(Decimal("0.05"), from_compounding="annual", to_compounding="semiannual")
        == expected_semiannual
    )

    with pytest.raises(InvalidRateError):
        accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="unsupported")
    with pytest.raises(InvalidRateError):
        discount_factor(Decimal("-2"), Decimal("1"))
    with pytest.raises(InvalidRateError):
        equivalent_rate(Decimal("NaN"), from_compounding="annual", to_compounding="annual")


def test_rate_value_objects_and_day_count_conventions() -> None:
    effective = EffectiveRate(rate=Decimal("0.06"))
    nominal = NominalRate(rate=Decimal("0.06"), compounding="semiannual", frequency=2)
    zero = ZeroRate(rate=Decimal("0.03"), maturity=Decimal("2"))
    forward = ForwardRate(rate=Decimal("0.02"), start_tenor=Decimal("1"), end_tenor=Decimal("2"))

    assert effective.compounding == "annual"
    assert nominal.frequency == 2
    assert zero.maturity == Decimal("2")
    assert forward.start_tenor == Decimal("1")

    with pytest.raises(InvalidRateError):
        InterestRate(rate=Decimal("NaN"))
    with pytest.raises(InvalidRateError):
        InterestRate(rate=Decimal("0.01"), compounding="bad")


def test_root_finding_solvers_cover_valid_and_invalid_cases() -> None:
    result = bisection_solve(
        lambda x: x * x - Decimal("4"), Decimal("0"), Decimal("3"), tolerance=Decimal("1e-8")
    )
    assert result.converged and result.method == "bisection"
    _assert_close(result.root, Decimal("2"))
    assert result.residual <= Decimal("1e-8")

    with pytest.raises(InvalidBracketError):
        bisection_solve(lambda x: x * x - Decimal("4"), Decimal("0"), Decimal("1"))
    with pytest.raises(InvalidBracketError):
        bisection_solve(
            lambda x: x * x - Decimal("2"),
            Decimal("0"),
            Decimal("1"),
            tolerance=Decimal("1e-12"),
            max_iterations=1,
        )

    with pytest.raises(ConvergenceError):
        newton_raphson_solve(
            lambda x: x * x + Decimal("1"),
            lambda x: Decimal("2") * x,
            Decimal("0.5"),
            tolerance=Decimal("1e-8"),
        )
    with pytest.raises(ConvergenceError):
        newton_raphson_solve(
            lambda x: x * x - Decimal("1"),
            lambda x: Decimal("0"),
            Decimal("0.5"),
            tolerance=Decimal("1e-8"),
        )

    brent_result = brent_solve(
        lambda x: x * x - Decimal("4"), Decimal("0"), Decimal("3"), tolerance=Decimal("1e-8")
    )
    assert brent_result.converged and brent_result.method == "brent"
    _assert_close(brent_result.root, Decimal("2"))

    with pytest.raises(InvalidBracketError):
        brent_solve(
            lambda x: x * x + Decimal("1"), Decimal("0"), Decimal("1"), tolerance=Decimal("1e-8")
        )


def test_yield_and_irr_handlers() -> None:
    cash_flows = [
        CashFlow(date(2024, 1, 1), Decimal("-100"), "USD"),
        CashFlow(date(2025, 1, 1), Decimal("110"), "USD"),
    ]
    summary = yield_to_maturity(cash_flows, Decimal("100"), settlement_date=date(2024, 1, 1))
    assert summary.converged
    assert summary.rate < Decimal("0")

    irr = internal_rate_of_return(cash_flows, settlement_date=date(2024, 1, 1))
    assert irr > Decimal("0")
    assert money_weighted_return(cash_flows, settlement_date=date(2024, 1, 1)) > Decimal("0")

    with pytest.raises(InvalidCashFlowError):
        yield_to_maturity([], Decimal("100"), settlement_date=date(2024, 1, 1))
    with pytest.raises(InvalidCashFlowError):
        internal_rate_of_return([], settlement_date=date(2024, 1, 1))


def test_interpolation_and_curve_point_validation() -> None:
    assert interpolate_linear(
        [Decimal("0"), Decimal("2")], [Decimal("0"), Decimal("4")], Decimal("1")
    ) == Decimal("2")
    assert interpolate_linear(
        [Decimal("0"), Decimal("2")],
        [Decimal("0"), Decimal("4")],
        Decimal("0"),
        extrapolation="constant",
    ) == Decimal("0")
    assert interpolate_logarithmic(
        [Decimal("1"), Decimal("2")], [Decimal("1"), Decimal("4")], Decimal("1.5")
    ) == Decimal("2")

    with pytest.raises(InterpolationError):
        interpolate_linear([Decimal("0"), Decimal("2")], [Decimal("1"), Decimal("3")], Decimal("3"))
    with pytest.raises(InterpolationError):
        interpolate_logarithmic(
            [Decimal("0"), Decimal("2")], [Decimal("1"), Decimal("3")], Decimal("3")
        )
    with pytest.raises(InterpolationError):
        interpolate_linear([Decimal("0"), Decimal("0")], [Decimal("1"), Decimal("2")], Decimal("1"))
    with pytest.raises(InterpolationError):
        interpolate_linear([Decimal("0"), Decimal("2")], [Decimal("1")], Decimal("1"))

    curve = YieldCurve(
        valuation_date=date(2024, 1, 1),
        currency="USD",
        points=(
            CurvePoint(Decimal("1"), Decimal("0.04")),
            CurvePoint(Decimal("2"), Decimal("0.05")),
        ),
        extrapolation_policy="constant",
    )
    assert curve.zero_rate(Decimal("1.5")) == Decimal("0.045")
    assert curve.discount_factor(Decimal("1")) < Decimal("1")
    assert curve.forward_rate(Decimal("1"), Decimal("2")) > Decimal("0")

    with pytest.raises(CurveConstructionError):
        YieldCurve(
            valuation_date=date(2024, 1, 1),
            currency="USD",
            points=(
                CurvePoint(Decimal("1"), Decimal("0.01")),
                CurvePoint(Decimal("1"), Decimal("0.02")),
            ),
        )
    with pytest.raises(CurveConstructionError):
        YieldCurve(
            valuation_date=date(2024, 1, 1),
            currency="USD",
            points=(
                CurvePoint(Decimal("2"), Decimal("0.02")),
                CurvePoint(Decimal("1"), Decimal("0.01")),
            ),
        )

    assert curve.zero_rate(Decimal("3")) == Decimal("0.05")


def test_curve_bootstrap_and_parametric_models() -> None:
    result = bootstrap_zero_curve(
        [(Decimal("1"), Decimal("95"), Decimal("100"))], tolerance=Decimal("0.1")
    )
    assert len(result.points) == 1
    assert len(result.residuals) == 1
    assert result.points[0].tenor == Decimal("1")

    with pytest.raises(BootstrapError):
        bootstrap_zero_curve([])

    assert nelson_siegel_zero_rate(
        Decimal("0"),
        beta0=Decimal("0.01"),
        beta1=Decimal("0.02"),
        beta2=Decimal("0.03"),
        tau=Decimal("1"),
    ) == Decimal("0.01")
    assert svensson_zero_rate(
        Decimal("0"),
        beta0=Decimal("0.01"),
        beta1=Decimal("0.02"),
        beta2=Decimal("0.03"),
        beta3=Decimal("0.04"),
        tau1=Decimal("1"),
        tau2=Decimal("2"),
    ) == Decimal("0.01")
    assert (
        len(
            nelson_siegel_curve(
                [Decimal("0"), Decimal("1")],
                beta0=Decimal("0.01"),
                beta1=Decimal("0.02"),
                beta2=Decimal("0.03"),
                tau=Decimal("1"),
            )
        )
        == 2
    )
    assert (
        len(
            svensson_curve(
                [Decimal("0"), Decimal("1")],
                beta0=Decimal("0.01"),
                beta1=Decimal("0.02"),
                beta2=Decimal("0.03"),
                beta3=Decimal("0.04"),
                tau1=Decimal("1"),
                tau2=Decimal("2"),
            )
        )
        == 2
    )

    with pytest.raises(InvalidRateError):
        nelson_siegel_zero_rate(
            Decimal("1"),
            beta0=Decimal("0.01"),
            beta1=Decimal("0.02"),
            beta2=Decimal("0.03"),
            tau=Decimal("0"),
        )
    with pytest.raises(InvalidRateError):
        svensson_zero_rate(
            Decimal("1"),
            beta0=Decimal("0.01"),
            beta1=Decimal("0.02"),
            beta2=Decimal("0.03"),
            beta3=Decimal("0.04"),
            tau1=Decimal("0"),
            tau2=Decimal("2"),
        )


def test_bond_metrics_reference_values_and_symmetric_shocks() -> None:
    accrued = accrued_interest(
        Decimal("0.05"), Decimal("1000"), days_since_last_coupon=30, days_in_period=180
    )
    with pytest.raises(InvalidCashFlowError):
        accrued_interest(
            Decimal("0.05"), Decimal("1000"), days_since_last_coupon=-1, days_in_period=180
        )
    with pytest.raises(InvalidCashFlowError):
        accrued_interest(
            Decimal("0.05"), Decimal("1000"), days_since_last_coupon=30, days_in_period=0
        )
    assert accrued == Decimal("8.333333333333333333")
    assert dirty_price(Decimal("95"), accrued) == Decimal("103.333333333333333333")
    assert clean_price(Decimal("103.333333333333333333"), accrued) == Decimal("95")

    cash_flows = [(Decimal("1"), Decimal("100")), (Decimal("2"), Decimal("1100"))]
    assert macaulay_duration(cash_flows, Decimal("0.05")) > Decimal("0")
    assert modified_duration(cash_flows, Decimal("0.05")) > Decimal("0")
    assert convexity(cash_flows, Decimal("0.05")) > Decimal("0")
    assert dv01(cash_flows, Decimal("0.05")) > Decimal("0")
    assert pvbp(cash_flows, Decimal("0.05")) > Decimal("0")

    up = effective_duration(cash_flows, Decimal("0.05"), shock=Decimal("0.001"))
    down = effective_duration(cash_flows, Decimal("0.05"), shock=Decimal("-0.001"))
    _assert_close(up, down)


def test_additional_branch_and_exception_paths() -> None:
    rate = InterestRate(rate=Decimal("0.03"), compounding="monthly", frequency=12)
    flow = CashFlow(payment_date=date(2025, 1, 1), amount=Decimal("100"), currency="USD")
    series = CashFlowSeries.from_cashflows([flow, CashFlow(date(2025, 6, 1), Decimal("50"), "USD")])

    assert present_value(
        flow, rate, valuation_date=date(2024, 1, 1), day_count_convention="ACTUAL_360"
    ) > Decimal("0")
    assert future_value(
        flow, rate, valuation_date=date(2024, 1, 1), day_count_convention="ACTUAL_360"
    ) > Decimal("0")
    assert present_value_series(series, rate, valuation_date=date(2024, 1, 1)) > Decimal("0")
    assert future_value_series(series, rate, valuation_date=date(2024, 1, 1)) > Decimal("0")
    assert present_value(flow, Decimal("0.05")) > Decimal("0")
    assert future_value(flow, Decimal("0.05")) > Decimal("0")
    assert present_value_series(
        (flow, CashFlow(date(2025, 12, 1), Decimal("20"), "USD")), Decimal("0.05")
    ) > Decimal("0")
    assert future_value_series(
        (flow, CashFlow(date(2025, 12, 1), Decimal("20"), "USD")), Decimal("0.05")
    ) > Decimal("0")

    with pytest.raises(InvalidCashFlowError):
        present_value(flow, rate, valuation_date=date(2024, 1, 1), day_count_convention="BAD")
    with pytest.raises(InvalidCashFlowError):
        future_value(flow, rate, valuation_date=date(2024, 1, 1), day_count_convention="BAD")

    with pytest.raises(InvalidRateError):
        InterestRate(rate=Decimal("0.03"), compounding="unsupported")
    with pytest.raises(InvalidRateError):
        InterestRate(rate=Decimal("0.03"), frequency=0)
    with pytest.raises(InvalidRateError):
        InterestRate(rate=Decimal("0.03"), day_count_convention="bad")

    assert equivalent_rate(
        Decimal("0.05"), from_compounding="continuous", to_compounding="annual"
    ) > Decimal("0")
    assert equivalent_rate(
        Decimal("0.05"), from_compounding="simple", to_compounding="simple"
    ) == Decimal("0.05")
    assert equivalent_rate(
        Decimal("0.05"), from_compounding="annual", to_compounding="continuous"
    ) > Decimal("0")
    assert equivalent_rate(
        Decimal("0.05"), from_compounding="simple", to_compounding="annual"
    ) == Decimal("0.05")
    assert accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="quarterly") > Decimal(
        "1"
    )
    assert accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="monthly") > Decimal("1")
    assert discount_factor(Decimal("0.05"), Decimal("1"), compounding="quarterly") < Decimal("1")
    with pytest.raises(InvalidRateError):
        accumulation_factor(Decimal("0.05"), Decimal("1"), compounding="annual", frequency=0)

    with pytest.raises(InterpolationError):
        interpolate_logarithmic(
            [Decimal("1"), Decimal("2")], [Decimal("1"), Decimal("4")], Decimal("0.5")
        )
    with pytest.raises(InterpolationError):
        interpolate_logarithmic([Decimal("1"), Decimal("2")], [Decimal("1")], Decimal("1"))
    with pytest.raises(InterpolationError):
        interpolate_logarithmic(
            [Decimal("1"), Decimal("2")], [Decimal("1"), Decimal("-1")], Decimal("1.5")
        )
    assert interpolate_logarithmic(
        [Decimal("1"), Decimal("2")], [Decimal("1"), Decimal("4")], Decimal("1")
    ) == Decimal("1")
    assert interpolate_logarithmic(
        [Decimal("1"), Decimal("2")],
        [Decimal("1"), Decimal("4")],
        Decimal("2"),
        extrapolation="constant",
    ) == Decimal("4")
    with pytest.raises(InterpolationError):
        interpolate_linear([Decimal("0"), Decimal("0")], [Decimal("1"), Decimal("2")], Decimal("1"))

    with pytest.raises(InvalidRateError):
        convexity([(Decimal("1"), Decimal("100"))], Decimal("-1"))
    with pytest.raises(InvalidRateError):
        modified_duration([(Decimal("1"), Decimal("100"))], Decimal("-1"))
    with pytest.raises(InvalidRateError):
        pvbp([(Decimal("1"), Decimal("100"))], Decimal("0.05"), shock=Decimal("0"))
    with pytest.raises(InvalidRateError):
        dv01([(Decimal("1"), Decimal("100"))], Decimal("0.05"), shock=Decimal("0"))
    with pytest.raises(InvalidRateError):
        effective_duration([(Decimal("1"), Decimal("100"))], Decimal("0.05"), shock=Decimal("0"))
    with pytest.raises(InvalidRateError):
        effective_duration([(Decimal("1"), Decimal("100"))], Decimal("-1"))
    with pytest.raises(InvalidRateError):
        macaulay_duration([(Decimal("1"), Decimal("-100"))], Decimal("0.05"))
    with pytest.raises(InvalidRateError):
        macaulay_duration([(Decimal("1"), Decimal("100"))], Decimal("-1"))
    with pytest.raises(InvalidRateError):
        convexity([(Decimal("1"), Decimal("-100"))], Decimal("0.05"))

    assert bisection_solve(lambda x: x - Decimal("2"), Decimal("2"), Decimal("3")).root == Decimal(
        "2"
    )
    assert bisection_solve(
        lambda x: x - Decimal("2"), Decimal("0"), Decimal("4"), tolerance=Decimal("1e-8")
    ).root == Decimal("2")
    with pytest.raises(InvalidBracketError):
        bisection_solve(lambda x: x * x - Decimal("4"), Decimal("0"), Decimal("0"))
    assert newton_raphson_solve(
        lambda x: x - Decimal("2"), lambda x: Decimal("1"), Decimal("2")
    ).converged
    with pytest.raises(ConvergenceError):
        newton_raphson_solve(
            lambda x: x * x + Decimal("1"),
            lambda x: Decimal("2") * x,
            Decimal("0"),
            tolerance=Decimal("1e-8"),
        )
    with pytest.raises(InvalidBracketError):
        brent_solve(lambda x: x - Decimal("1"), Decimal("2"), Decimal("2"))
    with pytest.raises(InvalidBracketError):
        brent_solve(lambda x: x * x + Decimal("1"), Decimal("0"), Decimal("1"))

    curve = YieldCurve(
        valuation_date=date(2024, 1, 1),
        currency="USD",
        points=(
            CurvePoint(Decimal("1"), Decimal("0.04")),
            CurvePoint(Decimal("2"), Decimal("0.05")),
        ),
        extrapolation_policy="constant",
    )
    assert curve.zero_rate(Decimal("0")) == Decimal("0.04")
    assert curve.zero_rate(Decimal("3")) == Decimal("0.05")
    with pytest.raises(CurveConstructionError):
        YieldCurve(
            valuation_date=date(2024, 1, 1),
            currency="",
            points=(CurvePoint(Decimal("1"), Decimal("0.01")),),
        )
    with pytest.raises(CurveConstructionError):
        YieldCurve(
            valuation_date=date(2024, 1, 1),
            currency="USD",
            day_count_convention="BAD",
            points=(CurvePoint(Decimal("1"), Decimal("0.01")),),
        )

    with pytest.raises(BootstrapError):
        bootstrap_zero_curve([(Decimal("0"), Decimal("95"), Decimal("100"))])
    with pytest.raises(BootstrapError):
        bootstrap_zero_curve([(Decimal("1"), Decimal("0"), Decimal("100"))])
    with pytest.raises(BootstrapError):
        bootstrap_zero_curve([(Decimal("1"), Decimal("95"), Decimal("0"))])
    with pytest.raises(BootstrapError):
        bootstrap_zero_curve(
            [(Decimal("1"), Decimal("50"), Decimal("100"))], tolerance=Decimal("0.001")
        )

    with pytest.raises(InvalidCashFlowError):
        CashFlow(payment_date=None, amount=Decimal("1"), currency="USD")
    with pytest.raises(InvalidCashFlowError):
        CashFlow(payment_date=date(2024, 1, 1), amount=Decimal("1"), currency=" ")

    mixed_series = CashFlowSeries.from_cashflows(
        [
            CashFlow(date(2024, 1, 1), Decimal("10"), "USD"),
            CashFlow(date(2024, 1, 1), Decimal("20"), "EUR"),
        ]
    )
    aggregated = mixed_series.aggregate_duplicates(fx_conversion=lambda _from, _to, amount: amount)
    assert aggregated.total_amount() == Decimal("30")

    cash_flows = [
        CashFlow(date(2024, 1, 1), Decimal("-100"), "USD"),
        CashFlow(date(2025, 1, 1), Decimal("110"), "USD"),
    ]
    assert internal_rate_of_return(cash_flows) > Decimal("0")
    assert yield_to_maturity(cash_flows, Decimal("100")).converged
    with pytest.raises(ConvergenceError):
        yield_to_maturity(
            cash_flows,
            Decimal("100"),
            solver=lambda _function, _lower, _upper, **_kwargs: ConvergenceResult(
                root=Decimal("0"),
                iterations=1,
                converged=False,
                residual=Decimal("1"),
                method="custom",
            ),
        )
