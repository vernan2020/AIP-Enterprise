from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable, Iterable

from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.financial_math.cashflows.cashflow_series import CashFlowSeries
from aip.domain.financial_math.exceptions import ConvergenceError, InvalidCashFlowError
from aip.domain.financial_math.root_finding.bisection import bisection_solve


@dataclass(frozen=True, slots=True)
class YieldSummary:
    rate: Decimal
    iterations: int
    converged: bool
    residual: Decimal
    method: str = "bisection"


def yield_to_maturity(
    cash_flow_series: CashFlowSeries | Iterable[CashFlow],
    price: Decimal,
    *,
    settlement_date: date | None = None,
    tolerance: Decimal = Decimal("1e-10"),
    max_iterations: int = 100,
    solver: Callable[[Callable[[Decimal], Decimal], Decimal, Decimal], object] | None = None,
) -> YieldSummary:
    if isinstance(cash_flow_series, CashFlowSeries):
        cash_flows = cash_flow_series.cash_flows
    else:
        cash_flows = tuple(cash_flow_series)
    if not cash_flows:
        raise InvalidCashFlowError("Cash flow series cannot be empty")
    if settlement_date is None:
        settlement_date = min(cash_flow.payment_date for cash_flow in cash_flows)

    def function(rate: Decimal) -> Decimal:
        present_value = Decimal("0")
        for cash_flow in cash_flows:
            years = Decimal((cash_flow.payment_date - settlement_date).days) / Decimal("365")
            present_value += cash_flow.amount / ((Decimal("1") + rate) ** years)
        return present_value - price

    result = (solver or bisection_solve)(function, Decimal("-0.99"), Decimal("1"), tolerance=tolerance, max_iterations=max_iterations)
    if not result.converged:
        raise ConvergenceError("Yield-to-maturity did not converge")
    return YieldSummary(rate=result.root, iterations=result.iterations, converged=result.converged, residual=result.residual, method=result.method)
