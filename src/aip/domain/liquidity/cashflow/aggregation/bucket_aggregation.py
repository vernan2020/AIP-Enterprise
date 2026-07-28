from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow


class BucketAggregation:
    """Aggregate projected cash flows by bucket."""

    def aggregate(self, cashflows: tuple[ProjectedCashFlow, ...]) -> dict[str, Decimal]:
        grouped: dict[str, Decimal] = {}
        for cashflow in cashflows:
            bucket = getattr(cashflow, "bucket", "default")
            grouped[bucket] = grouped.get(bucket, Decimal("0")) + cashflow.amount
        return grouped
