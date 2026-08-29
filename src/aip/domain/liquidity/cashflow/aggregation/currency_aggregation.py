from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow


class CurrencyAggregation:
    """Aggregate projected cash flows by currency."""

    def aggregate(self, cashflows: tuple[ProjectedCashFlow, ...]) -> dict[str, Decimal]:
        grouped: dict[str, Decimal] = {}
        for cashflow in cashflows:
            grouped[cashflow.currency] = (
                grouped.get(cashflow.currency, Decimal("0")) + cashflow.amount
            )
        return grouped
