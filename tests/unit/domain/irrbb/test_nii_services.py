from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
)
from aip.domain.irrbb.nii import (
    NetInterestIncomeResult,
    NIIAccrualAmountStatus,
    NIIAccrualType,
    NIIBalanceSheetAssumption,
    NIIInterestAccrual,
    NIIProjectionBasis,
    NIIRepricingTrace,
    NIIShockTiming,
)
from aip.domain.irrbb.services.delta_nii_service import DeltaNIIService
from aip.domain.irrbb.services.net_interest_income_service import NetInterestIncomeService
from aip.shared.money import Currency, Money


class _ScenarioFXProvider:
    def __init__(self, rate: Decimal) -> None:
        self._rate = rate
        self.calls: list[tuple[Currency, Currency, IRRBBScenario, date, date]] = []

    def rate(
        self,
        *,
        from_currency: Currency,
        to_currency: Currency,
        scenario: IRRBBScenario,
        valuation_date: date,
        accrual_end_date: date,
    ) -> Decimal:
        self.calls.append(
            (
                from_currency,
                to_currency,
                scenario,
                valuation_date,
                accrual_end_date,
            )
        )
        return self._rate


def _methodology() -> IRRBBMethodologyProfile:
    return IRRBBMethodologyProfile(
        code="INTERNAL-NII",
        version="2026.09.10",
        status=IRRBBMethodologyStatus.INTERNAL,
        source_reference="policy:nii",
    )


def _basis(*, horizon_end: date = date(2027, 9, 10)) -> NIIProjectionBasis:
    return NIIProjectionBasis(
        methodology=_methodology(),
        valuation_date=date(2026, 9, 10),
        horizon_end_date=horizon_end,
        balance_sheet_assumption=NIIBalanceSheetAssumption.CONSTANT,
        shock_timing=NIIShockTiming.INSTANTANEOUS,
        source_reference="projection:approved-input",
    )


def _accrual(
    *,
    accrual_id: str,
    scenario: IRRBBScenario,
    accrual_type: NIIAccrualType,
    amount: Money,
    start: date = date(2026, 9, 10),
    end: date = date(2026, 10, 10),
) -> NIIInterestAccrual:
    return NIIInterestAccrual(
        accrual_id=accrual_id,
        position_id=f"position:{accrual_id}",
        scenario=scenario,
        accrual_type=accrual_type,
        amount=amount,
        accrual_start_date=start,
        accrual_end_date=end,
        source_reference=f"source:{accrual_id}",
    )


def _result(
    *,
    basis: NIIProjectionBasis,
    scenario: IRRBBScenario,
    amount: str,
    currency: Currency = Currency.CRC,
) -> NetInterestIncomeResult:
    return NetInterestIncomeService.calculate(
        accruals=(
            _accrual(
                accrual_id=f"result:{scenario.value}",
                scenario=scenario,
                accrual_type=NIIAccrualType.INTEREST_INCOME,
                amount=Money(Decimal(amount), currency),
            ),
        ),
        basis=basis,
        scenario=scenario,
        reporting_currency=currency,
    )


def test_projection_basis_rejects_non_forward_horizon() -> None:
    with pytest.raises(ValueError, match="horizon_end_date"):
        _basis(horizon_end=date(2026, 9, 10))


def test_repricing_trace_rejects_non_finite_applied_rate() -> None:
    with pytest.raises(ValueError, match="applied_rate must be finite"):
        NIIRepricingTrace(
            rate_reference="TRI-CRC",
            repricing_date=date(2026, 10, 10),
            pricing_tenor_months=12,
            applied_rate=Decimal("NaN"),
            source_reference="curve:tri-crc",
        )


def test_accrual_rejects_non_finite_amount() -> None:
    with pytest.raises(ValueError, match="accrual amount must be finite"):
        _accrual(
            accrual_id="non-finite",
            scenario=IRRBBScenario.BASE,
            accrual_type=NIIAccrualType.INTEREST_INCOME,
            amount=Money(Decimal("Infinity"), Currency.CRC),
        )


def test_rate_projected_accrual_requires_trace_and_projection_basis() -> None:
    with pytest.raises(ValueError, match="repricing_trace"):
        NIIInterestAccrual(
            accrual_id="a1",
            position_id="p1",
            scenario=IRRBBScenario.PARALLEL_UP,
            accrual_type=NIIAccrualType.INTEREST_INCOME,
            amount=Money(Decimal("10"), Currency.CRC),
            accrual_start_date=date(2026, 10, 10),
            accrual_end_date=date(2026, 11, 10),
            source_reference="source:a1",
            amount_status=NIIAccrualAmountStatus.RATE_PROJECTED,
        )

    trace = NIIRepricingTrace(
        rate_reference="TRI-CRC",
        repricing_date=date(2026, 10, 10),
        pricing_tenor_months=12,
        applied_rate=Decimal("0.055"),
        source_reference="curve:tri-crc",
    )
    with pytest.raises(ValueError, match="projection_basis"):
        NIIInterestAccrual(
            accrual_id="a2",
            position_id="p2",
            scenario=IRRBBScenario.PARALLEL_UP,
            accrual_type=NIIAccrualType.INTEREST_INCOME,
            amount=Money(Decimal("10"), Currency.CRC),
            accrual_start_date=date(2026, 10, 10),
            accrual_end_date=date(2026, 11, 10),
            source_reference="source:a2",
            amount_status=NIIAccrualAmountStatus.RATE_PROJECTED,
            repricing_trace=trace,
        )


def test_rate_projected_accrual_rejects_mid_period_repricing() -> None:
    trace = NIIRepricingTrace(
        rate_reference="TRI-CRC",
        repricing_date=date(2026, 10, 15),
        pricing_tenor_months=12,
        applied_rate=Decimal("0.055"),
        source_reference="curve:tri-crc",
    )

    with pytest.raises(ValueError, match="split the accrual"):
        NIIInterestAccrual(
            accrual_id="a1",
            position_id="p1",
            scenario=IRRBBScenario.PARALLEL_UP,
            accrual_type=NIIAccrualType.INTEREST_INCOME,
            amount=Money(Decimal("10"), Currency.CRC),
            accrual_start_date=date(2026, 10, 10),
            accrual_end_date=date(2026, 11, 10),
            source_reference="source:a1",
            amount_status=NIIAccrualAmountStatus.RATE_PROJECTED,
            repricing_trace=trace,
            projection_basis="curve+spread",
        )


def test_net_interest_income_aggregates_explicit_accruals_and_scenario_fx() -> None:
    basis = _basis()
    fx = _ScenarioFXProvider(Decimal("500"))
    accruals = (
        _accrual(
            accrual_id="income-crc",
            scenario=IRRBBScenario.PARALLEL_UP,
            accrual_type=NIIAccrualType.INTEREST_INCOME,
            amount=Money(Decimal("1250"), Currency.CRC),
        ),
        _accrual(
            accrual_id="expense-usd",
            scenario=IRRBBScenario.PARALLEL_UP,
            accrual_type=NIIAccrualType.INTEREST_EXPENSE,
            amount=Money(Decimal("2"), Currency.USD),
        ),
    )

    result = NetInterestIncomeService.calculate(
        accruals=accruals,
        basis=basis,
        scenario=IRRBBScenario.PARALLEL_UP,
        reporting_currency=Currency.CRC,
        exchange_rates=fx,
    )

    assert result.interest_income.amount == Decimal("1250")
    assert result.interest_expense.amount == Decimal("1000")
    assert result.net_interest_income.amount == Decimal("250")
    assert result.accruals[0].exchange_rate == Decimal("1")
    assert result.accruals[1].signed_nii_contribution.amount == Decimal("-1000")
    assert fx.calls == [
        (
            Currency.USD,
            Currency.CRC,
            IRRBBScenario.PARALLEL_UP,
            date(2026, 9, 10),
            date(2026, 10, 10),
        )
    ]


def test_net_interest_income_preserves_negative_interest_amounts() -> None:
    result = NetInterestIncomeService.calculate(
        accruals=(
            _accrual(
                accrual_id="negative-income",
                scenario=IRRBBScenario.BASE,
                accrual_type=NIIAccrualType.INTEREST_INCOME,
                amount=Money(Decimal("-100"), Currency.CRC),
            ),
            _accrual(
                accrual_id="expense",
                scenario=IRRBBScenario.BASE,
                accrual_type=NIIAccrualType.INTEREST_EXPENSE,
                amount=Money(Decimal("50"), Currency.CRC),
            ),
        ),
        basis=_basis(),
        scenario=IRRBBScenario.BASE,
        reporting_currency=Currency.CRC,
    )

    assert result.net_interest_income.amount == Decimal("-150")


def test_net_interest_income_rejects_missing_fx_duplicate_and_horizon_leakage() -> None:
    basis = _basis()
    usd = _accrual(
        accrual_id="usd",
        scenario=IRRBBScenario.BASE,
        accrual_type=NIIAccrualType.INTEREST_INCOME,
        amount=Money(Decimal("1"), Currency.USD),
    )
    with pytest.raises(ValueError, match="exchange-rate provider"):
        NetInterestIncomeService.calculate(
            accruals=(usd,),
            basis=basis,
            scenario=IRRBBScenario.BASE,
            reporting_currency=Currency.CRC,
        )

    duplicate = _accrual(
        accrual_id="same",
        scenario=IRRBBScenario.BASE,
        accrual_type=NIIAccrualType.INTEREST_INCOME,
        amount=Money(Decimal("1"), Currency.CRC),
    )
    with pytest.raises(ValueError, match="duplicate NII accrual_id"):
        NetInterestIncomeService.calculate(
            accruals=(duplicate, duplicate),
            basis=basis,
            scenario=IRRBBScenario.BASE,
            reporting_currency=Currency.CRC,
        )

    outside = _accrual(
        accrual_id="outside",
        scenario=IRRBBScenario.BASE,
        accrual_type=NIIAccrualType.INTEREST_INCOME,
        amount=Money(Decimal("1"), Currency.CRC),
        start=date(2027, 9, 10),
        end=date(2027, 10, 10),
    )
    with pytest.raises(ValueError, match="projection horizon"):
        NetInterestIncomeService.calculate(
            accruals=(outside,),
            basis=basis,
            scenario=IRRBBScenario.BASE,
            reporting_currency=Currency.CRC,
        )


@pytest.mark.parametrize(
    "fx_rate",
    [Decimal("0"), Decimal("NaN"), Decimal("Infinity")],
)
def test_net_interest_income_rejects_invalid_fx(fx_rate: Decimal) -> None:
    usd = _accrual(
        accrual_id="usd",
        scenario=IRRBBScenario.BASE,
        accrual_type=NIIAccrualType.INTEREST_INCOME,
        amount=Money(Decimal("1"), Currency.USD),
    )

    with pytest.raises(ValueError, match="finite and positive"):
        NetInterestIncomeService.calculate(
            accruals=(usd,),
            basis=_basis(),
            scenario=IRRBBScenario.BASE,
            reporting_currency=Currency.CRC,
            exchange_rates=_ScenarioFXProvider(fx_rate),
        )


def test_net_interest_income_result_rejects_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="reporting_currency"):
        NetInterestIncomeResult(
            basis=_basis(),
            scenario=IRRBBScenario.BASE,
            reporting_currency=Currency.CRC,
            interest_income=Money(Decimal("1"), Currency.USD),
            interest_expense=Money(Decimal("0"), Currency.CRC),
            net_interest_income=Money(Decimal("1"), Currency.CRC),
            accruals=(),
        )


def test_net_interest_income_result_rejects_unreconciled_total() -> None:
    valid = _result(
        basis=_basis(),
        scenario=IRRBBScenario.BASE,
        amount="100",
    )

    with pytest.raises(ValueError, match="net_interest_income"):
        NetInterestIncomeResult(
            basis=valid.basis,
            scenario=valid.scenario,
            reporting_currency=valid.reporting_currency,
            interest_income=valid.interest_income,
            interest_expense=valid.interest_expense,
            net_interest_income=Money(Decimal("99"), Currency.CRC),
            accruals=valid.accruals,
        )


def test_delta_nii_calculates_requested_stresses_and_worst_fall() -> None:
    basis = _basis()
    result = DeltaNIIService.calculate(
        base=_result(basis=basis, scenario=IRRBBScenario.BASE, amount="100"),
        stressed=(
            _result(basis=basis, scenario=IRRBBScenario.PARALLEL_UP, amount="75"),
            _result(basis=basis, scenario=IRRBBScenario.PARALLEL_DOWN, amount="115"),
        ),
        required_scenarios=(
            IRRBBScenario.PARALLEL_UP,
            IRRBBScenario.PARALLEL_DOWN,
        ),
    )

    assert result.base_nii.amount == Decimal("100")
    assert result.worst_scenario is IRRBBScenario.PARALLEL_UP
    assert result.worst_loss.amount == Decimal("25")
    assert [assessment.delta_nii.amount for assessment in result.assessments] == [
        Decimal("-25"),
        Decimal("15"),
    ]


def test_delta_nii_rejects_mismatched_basis_and_unrequested_scenario() -> None:
    basis = _basis()
    other_basis = NIIProjectionBasis(
        methodology=_methodology(),
        valuation_date=date(2026, 9, 10),
        horizon_end_date=date(2027, 6, 30),
        balance_sheet_assumption=NIIBalanceSheetAssumption.CONSTANT,
        shock_timing=NIIShockTiming.INSTANTANEOUS,
        source_reference="projection:approved-input",
    )

    with pytest.raises(ValueError, match="same projection basis"):
        DeltaNIIService.calculate(
            base=_result(basis=basis, scenario=IRRBBScenario.BASE, amount="100"),
            stressed=(
                _result(
                    basis=other_basis,
                    scenario=IRRBBScenario.PARALLEL_UP,
                    amount="90",
                ),
            ),
            required_scenarios=(IRRBBScenario.PARALLEL_UP,),
        )

    with pytest.raises(ValueError, match="unexpected NII stress scenarios"):
        DeltaNIIService.calculate(
            base=_result(basis=basis, scenario=IRRBBScenario.BASE, amount="100"),
            stressed=(
                _result(basis=basis, scenario=IRRBBScenario.PARALLEL_UP, amount="90"),
                _result(basis=basis, scenario=IRRBBScenario.STEEPENER, amount="80"),
            ),
            required_scenarios=(IRRBBScenario.PARALLEL_UP,),
        )
