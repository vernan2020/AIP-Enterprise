from __future__ import annotations

from aip.domain.liquidity.cashflow.exceptions import BehavioralError, ProjectionError
from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest


class BehavioralProjection:
    """Apply configurable behavioral assumptions to contractual cash flows."""

    def project(self, request: ProjectionRequest, parent_results: list[object] | None = None) -> tuple[ProjectedCashFlow, ...]:
        if not request.behavioral_assumptions:
            raise BehavioralError("Behavioral assumptions are required")
        assumption_names = {assumption.name for assumption in request.behavioral_assumptions}
        if len(assumption_names) != len(request.behavioral_assumptions):
            raise BehavioralError("Conflicting behavioral assumptions are not allowed")
        parent_result = parent_results[0] if parent_results else None
        base_cashflows: tuple[ProjectedCashFlow, ...] = ()
        if isinstance(parent_result, ProjectionRequest):
            base_cashflows = tuple(
                self._as_projected_cashflow(cash_flow)
                for cash_flow in parent_result.contractual_cashflows
            )
        elif isinstance(parent_result, tuple):
            base_cashflows = tuple(self._as_projected_cashflow(cash_flow) for cash_flow in parent_result)
        elif parent_result is not None:
            base_cashflows = (self._as_projected_cashflow(parent_result),)
        if not base_cashflows:
            raise ProjectionError("A contractual projection is required for behavioral adjustment")
        adjusted: list[ProjectedCashFlow] = []
        for cash_flow in base_cashflows:
            if cash_flow.amount <= 0:
                continue
            for assumption in tuple(request.behavioral_assumptions):
                adjusted_amount = cash_flow.amount * assumption.probability * assumption.effect_ratio
                adjusted.append(
                    ProjectedCashFlow(
                        payment_date=cash_flow.payment_date,
                        amount=adjusted_amount,
                        currency=cash_flow.currency,
                        cash_flow_type=cash_flow.cash_flow_type,
                        source="behavioral",
                        probability=assumption.probability,
                        bucket=cash_flow.bucket,
                    )
                )
        if not adjusted:
            raise BehavioralError("Behavioral projection produced no cash flows")
        return tuple(adjusted)

    def _as_projected_cashflow(self, cash_flow: object) -> ProjectedCashFlow:
        if isinstance(cash_flow, ProjectedCashFlow):
            return cash_flow
        return ProjectedCashFlow(
            payment_date=getattr(cash_flow, "payment_date"),
            amount=getattr(cash_flow, "amount"),
            currency=getattr(cash_flow, "currency", "USD"),
            cash_flow_type=getattr(cash_flow, "cash_flow_type", "coupon"),
            source="contractual",
            bucket=getattr(cash_flow, "bucket", "default"),
        )
