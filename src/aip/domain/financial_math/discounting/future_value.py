from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.financial_math.cashflows.cashflow_series import CashFlowSeries
from aip.domain.financial_math.discounting.compounding import accumulation_factor
from aip.domain.financial_math.exceptions import InvalidCashFlowError
from aip.domain.financial_math.rates.interest_rate import InterestRate


def future_value(
    cash_flow: CashFlow,
    rate: Decimal | InterestRate,
    *,
    valuation_date: date | None = None,
    compounding: str = "annual",
    frequency: int = 1,
    day_count_convention: str = "ACTUAL_365",
) -> Decimal:
    if valuation_date is None:
        valuation_date = date.today()
    rate_value = rate.rate if isinstance(rate, InterestRate) else rate
    compounding_value = rate.compounding if isinstance(rate, InterestRate) else compounding
    frequency_value = rate.frequency if isinstance(rate, InterestRate) else frequency
    if day_count_convention.upper() not in {"ACTUAL_365", "ACTUAL_360"}:
        raise InvalidCashFlowError("Unsupported day-count convention")
    time = Decimal((cash_flow.payment_date - valuation_date).days) / Decimal("365")
    return cash_flow.amount * accumulation_factor(rate_value, time, compounding=compounding_value, frequency=frequency_value)


def future_value_series(
    cash_flow_series: CashFlowSeries | Iterable[CashFlow],
    rate: Decimal | InterestRate,
    *,
    valuation_date: date | None = None,
    compounding: str = "annual",
    frequency: int = 1,
    day_count_convention: str = "ACTUAL_365",
) -> Decimal:
    if isinstance(cash_flow_series, CashFlowSeries):
        cash_flows = cash_flow_series.cash_flows
    else:
        cash_flows = tuple(cash_flow_series)
    if not cash_flows:
        raise InvalidCashFlowError("Cash flow series cannot be empty")
    if valuation_date is None:
        valuation_date = date.today()
    return sum(
        future_value(
            cash_flow,
            rate,
            valuation_date=valuation_date,
            compounding=compounding,
            frequency=frequency,
            day_count_convention=day_count_convention,
        )
        for cash_flow in cash_flows
    )
