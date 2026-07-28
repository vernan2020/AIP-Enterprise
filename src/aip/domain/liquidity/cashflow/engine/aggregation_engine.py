from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.aggregation.bucket_aggregation import BucketAggregation
from aip.domain.liquidity.cashflow.aggregation.currency_aggregation import CurrencyAggregation
from aip.domain.liquidity.cashflow.aggregation.scenario_aggregation import ScenarioAggregation
from aip.domain.liquidity.cashflow.exceptions import AggregationError
from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest


class AggregationEngine:
    """Aggregate projected cash flows across multiple dimensions."""

    def __init__(self) -> None:
        self._bucket = BucketAggregation()
        self._currency = CurrencyAggregation()
        self._scenario = ScenarioAggregation()

    def aggregate(self, cashflows: tuple[ProjectedCashFlow, ...], request: ProjectionRequest) -> dict[str, dict[str, Decimal]]:
        if not cashflows:
            raise AggregationError("At least one projected cash flow is required")
        projected_cashflows = tuple(
            cashflow if isinstance(cashflow, ProjectedCashFlow) else ProjectedCashFlow(
                payment_date=cashflow.payment_date,
                amount=cashflow.amount,
                currency=cashflow.currency,
                cash_flow_type=cashflow.cash_flow_type,
                bucket=request.business_unit or "default",
            )
            for cashflow in cashflows
        )
        return {
            "bucket": self._bucket.aggregate(projected_cashflows),
            "currency": self._currency.aggregate(projected_cashflows),
            "scenario": self._scenario.aggregate(projected_cashflows),
            "product": {request.product_type or "default": self._sum_cashflows(projected_cashflows)},
            "counterparty": {request.counterparty or "default": self._sum_cashflows(projected_cashflows)},
            "instrument": {request.instrument_id or "default": self._sum_cashflows(projected_cashflows)},
            "portfolio": {request.portfolio_reference or "default": self._sum_cashflows(projected_cashflows)},
            "business_unit": {request.business_unit or "default": self._sum_cashflows(projected_cashflows)},
        }

    def _sum_cashflows(self, cashflows: tuple[ProjectedCashFlow, ...]) -> Decimal:
        return sum((cashflow.amount for cashflow in cashflows), Decimal("0"))
