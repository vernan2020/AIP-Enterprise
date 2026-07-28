from __future__ import annotations

from decimal import Decimal

from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.liquidity.cashflow.exceptions import ProjectionError
from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest


class ContractualProjection:
    """Project contractual cash flows without behavioral adjustments."""

    def project(self, request: ProjectionRequest) -> tuple[ProjectedCashFlow, ...]:
        if not request.contractual_cashflows:
            raise ProjectionError("At least one contractual cash flow is required")
        projected: list[ProjectedCashFlow] = []
        for cash_flow in request.contractual_cashflows:
            payment_date = getattr(cash_flow, "payment_date", None)
            if payment_date is None:
                raise ProjectionError("Payment date is required")
            if payment_date < request.valuation_date:
                continue
            amount = getattr(cash_flow, "amount", None)
            if amount is None:
                raise ProjectionError("Cash flow amount is required")
            if amount == 0:
                raise ProjectionError("Cash flow amounts cannot be zero")
            if amount < 0:
                raise ProjectionError("Cash flow amounts cannot be negative")
            projected.append(
                ProjectedCashFlow(
                    payment_date=payment_date,
                    amount=amount,
                    currency=getattr(cash_flow, "currency", "USD"),
                    cash_flow_type=getattr(cash_flow, "cash_flow_type", "coupon"),
                    source="contractual",
                    bucket=request.business_unit or "default",
                )
            )
        return tuple(projected)
