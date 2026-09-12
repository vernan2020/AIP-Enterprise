from __future__ import annotations

from datetime import date

from aip.domain.irrbb.models import BankingBookPosition, IRRBBCashFlow, RateType
from aip.domain.irrbb.ports import ContractualCashFlowScheduleProvider


class ExplicitScheduleCashFlowBuilder:
    """Adapt an approved normalized contractual schedule into IRRBB cash flows.

    This strategy is the safe default for amortizing credit, complex deposits,
    borrowings and off-balance contracts when a simple canonical position does
    not contain enough information to reconstruct exact payments.
    """

    def __init__(self, schedule_provider: ContractualCashFlowScheduleProvider) -> None:
        self._schedule_provider = schedule_provider

    def build(
        self,
        *,
        position: BankingBookPosition,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        records = self._schedule_provider.get_schedule(
            position=position,
            valuation_date=valuation_date,
        )
        cashflows: list[IRRBBCashFlow] = []

        for record in records:
            if record.amount.currency is not position.currency:
                raise ValueError(
                    f"schedule currency {record.amount.currency} does not match "
                    f"position currency {position.currency}"
                )
            if record.payment_date < valuation_date:
                raise ValueError("contractual schedule contains a past payment date")

            risk_date = record.risk_date or self._default_risk_date(
                position=position,
                payment_date=record.payment_date,
            )
            if risk_date < valuation_date:
                raise ValueError("contractual schedule contains a past risk date")

            cashflows.append(
                IRRBBCashFlow(
                    position_id=position.position_id,
                    side=position.side,
                    direction=record.direction,
                    amount=record.amount,
                    cashflow_date=record.payment_date,
                    risk_date=risk_date,
                    flow_type=record.flow_type,
                    source_reference=record.source_reference,
                    amount_status=record.amount_status,
                    projection_basis=record.projection_basis,
                )
            )

        cashflows.sort(key=lambda item: (item.cashflow_date, item.flow_type))
        return tuple(cashflows)

    @staticmethod
    def _default_risk_date(*, position: BankingBookPosition, payment_date: date) -> date:
        if position.rate_type is RateType.FIXED:
            return payment_date
        if position.next_repricing_date is None:
            raise ValueError("floating-rate position requires next_repricing_date")
        return min(payment_date, position.next_repricing_date)
