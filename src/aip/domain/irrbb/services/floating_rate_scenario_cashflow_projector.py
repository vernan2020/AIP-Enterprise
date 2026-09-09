from __future__ import annotations

from datetime import date

from aip.domain.irrbb.models import (
    BankingBookPosition,
    CashFlowAmountStatus,
    IRRBBCashFlow,
    IRRBBScenario,
    RateType,
)
from aip.domain.irrbb.ports import (
    FloatingRateCouponBasisProvider,
    ScenarioReferenceRateProvider,
)
from aip.shared.money import Money


class FloatingRateScenarioCashFlowProjector:
    """Reproject scenario-sensitive floating coupons under an IRRBB scenario.

    The projector never derives day-count conventions or notional bases. Those are
    supplied through ``FloatingRateCouponBasisProvider``. Reference index rates are
    supplied by a scenario-aware market/methodology provider. Principal and already
    contractual/source-provided cash flows are preserved unchanged.
    """

    def __init__(
        self,
        *,
        basis_provider: FloatingRateCouponBasisProvider,
        reference_rates: ScenarioReferenceRateProvider,
    ) -> None:
        self._basis_provider = basis_provider
        self._reference_rates = reference_rates

    def project(
        self,
        *,
        position: BankingBookPosition,
        base_cashflows: tuple[IRRBBCashFlow, ...],
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        self._validate_position_cashflows(position=position, cashflows=base_cashflows)

        if scenario is IRRBBScenario.BASE or position.rate_type is RateType.FIXED:
            return base_cashflows

        projected: list[IRRBBCashFlow] = []
        for flow in base_cashflows:
            if flow.amount_status is not CashFlowAmountStatus.PROJECTED_CURRENT_RATE:
                projected.append(flow)
                continue

            basis = self._basis_provider.basis_for(
                position=position,
                cashflow=flow,
                valuation_date=valuation_date,
            )
            if basis is None:
                raise ValueError(
                    f"missing floating-rate coupon basis for {flow.position_id} "
                    f"at {flow.cashflow_date.isoformat()}"
                )
            if basis.position_id != flow.position_id:
                raise ValueError("floating-rate coupon basis position_id does not match cash flow")
            if basis.cashflow_date != flow.cashflow_date:
                raise ValueError("floating-rate coupon basis cashflow_date does not match cash flow")
            if basis.notional.currency is not flow.amount.currency:
                raise ValueError("floating-rate coupon basis currency does not match cash flow")
            if basis.reset_date < valuation_date:
                raise ValueError(
                    "scenario-projected coupon basis reset_date cannot be before valuation_date; "
                    "already-reset coupons should be contractual/source-provided"
                )

            reference_rate = self._reference_rates.reference_rate(
                reference_rate_code=basis.reference_rate_code,
                currency=basis.notional.currency,
                scenario=scenario,
                reset_date=basis.reset_date,
                valuation_date=valuation_date,
            )
            effective_rate = basis.effective_rate(reference_rate)
            amount = basis.notional.amount * effective_rate * basis.accrual_fraction

            projected.append(
                IRRBBCashFlow(
                    position_id=flow.position_id,
                    side=flow.side,
                    direction=flow.direction,
                    amount=Money(amount, flow.amount.currency),
                    cashflow_date=flow.cashflow_date,
                    risk_date=flow.risk_date,
                    flow_type=flow.flow_type,
                    source_reference=flow.source_reference,
                    amount_status=CashFlowAmountStatus.SCENARIO_PROJECTED,
                    projection_basis=(
                        f"{basis.source_reference}|{basis.reference_rate_code}|"
                        f"RESET={basis.reset_date.isoformat()}|SCENARIO={scenario.value}"
                    ),
                )
            )

        return tuple(projected)

    @staticmethod
    def _validate_position_cashflows(
        *,
        position: BankingBookPosition,
        cashflows: tuple[IRRBBCashFlow, ...],
    ) -> None:
        for flow in cashflows:
            if flow.position_id != position.position_id:
                raise ValueError("all projected cash flows must belong to the supplied position")
            if flow.amount.currency is not position.currency:
                raise ValueError("cash-flow currency must match position currency")
