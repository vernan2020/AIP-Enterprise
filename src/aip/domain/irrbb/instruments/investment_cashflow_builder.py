from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    IRRBBCashFlow,
    IRRBBInstrumentClass,
    RateType,
)
from aip.domain.portfolio.services.portfolio_contractual_cashflow_service import (
    PortfolioContractualCashFlowService,
)
from aip.shared.money import Money


class InvestmentContractualCashFlowBuilder:
    """IRRBB adapter over AIP's canonical investment cash-flow service.

    The adapter intentionally delegates coupon dates and principal amounts to
    ``PortfolioContractualCashFlowService``. It only translates the canonical
    IRRBB position into the portfolio contract and adds IRRBB risk metadata.
    """

    _PERIODICITY_LABELS = {
        1: "mensual",
        2: "bimestral",
        3: "trimestral",
        4: "cuatrimestral",
        6: "semestral",
        12: "anual",
    }

    def build(
        self,
        *,
        position: BankingBookPosition,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        self._validate_position(position)

        periodicity = (
            self._PERIODICITY_LABELS[position.payment_frequency_months]
            if position.payment_frequency_months is not None
            else None
        )
        portfolio_position = {
            "maturity_date": position.maturity_date,
            "nominal": position.principal.amount,
            "currency": position.currency.value,
            "periodicity": periodicity,
            "nominal_rate": position.contractual_rate,
            "last_interest_payment_date": position.last_interest_payment_date,
            "variable_rate_flag": "S" if position.rate_type is RateType.FLOATING else "N",
        }
        contractual = PortfolioContractualCashFlowService.calculate(
            portfolio_position,
            valuation_date,
        )

        result: list[IRRBBCashFlow] = []
        for flow in contractual:
            if flow.currency.strip().upper() != position.currency.value:
                raise ValueError("portfolio cash-flow currency does not match IRRBB position")

            amount_status = (
                CashFlowAmountStatus.PROJECTED_CURRENT_RATE
                if flow.amount_status == "PROJECTED_CURRENT_RATE"
                else CashFlowAmountStatus.CONTRACTUAL
            )
            result.append(
                IRRBBCashFlow(
                    position_id=position.position_id,
                    side=position.side,
                    direction=CashFlowDirection.RECEIVABLE,
                    amount=Money(flow.amount_local, position.currency),
                    cashflow_date=flow.payment_date,
                    risk_date=self._risk_date(position, flow.payment_date),
                    flow_type=flow.flow_type,
                    source_reference=f"{position.source_reference}|{flow.source}",
                    amount_status=amount_status,
                    projection_basis=(
                        flow.source
                        if amount_status is CashFlowAmountStatus.PROJECTED_CURRENT_RATE
                        else None
                    ),
                )
            )

        return tuple(result)

    @classmethod
    def _validate_position(cls, position: BankingBookPosition) -> None:
        if position.instrument_class is not IRRBBInstrumentClass.INVESTMENT:
            raise ValueError("investment builder requires instrument_class=INVESTMENT")
        if position.side is not BankingBookSide.ASSET:
            raise ValueError("investment builder requires an asset position")
        if position.maturity_date is None:
            raise ValueError("investment position requires maturity_date")
        if position.contractual_rate is None:
            raise ValueError(
                "investment position requires explicit contractual_rate, including zero"
            )
        if position.contractual_rate != Decimal("0"):
            if position.payment_frequency_months is None:
                raise ValueError("interest-bearing investment requires payment_frequency_months")
            if position.payment_frequency_months not in cls._PERIODICITY_LABELS:
                raise ValueError("unsupported investment payment_frequency_months")
        if position.rate_type is RateType.FLOATING and position.next_repricing_date is None:
            raise ValueError("floating-rate investment requires next_repricing_date")

    @staticmethod
    def _risk_date(position: BankingBookPosition, payment_date: date) -> date:
        if position.rate_type is RateType.FIXED:
            return payment_date
        if position.next_repricing_date is None:
            raise ValueError("floating-rate investment requires next_repricing_date")
        return min(payment_date, position.next_repricing_date)
