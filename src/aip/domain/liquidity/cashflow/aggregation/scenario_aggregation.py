from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow


class ScenarioAggregation:
    """Aggregate projected cash flows by scenario."""

    def aggregate(self, cashflows: tuple[ProjectedCashFlow, ...]) -> dict[str, Decimal]:
        grouped: dict[str, Decimal] = {}
        for cashflow in cashflows:
            scenario = cashflow.scenario or "base"
            grouped[scenario] = grouped.get(scenario, Decimal("0")) + cashflow.amount
        return grouped
