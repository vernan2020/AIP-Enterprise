from __future__ import annotations

from calendar import monthrange
from datetime import date

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    IRRBBCashFlow,
    IRRBBInstrumentClass,
    IRRBBScenario,
    OptionalityType,
    PaymentStructure,
)
from aip.domain.irrbb.ports import NonMaturityDepositProfileProvider
from aip.shared.money import Money


class NonMaturityDepositBehavioralModel:
    """Replace contractual NMD maturity with an approved behavioral profile.

    No behavioral weights or tenors are embedded in this service. They are supplied
    by a versioned profile provider and may vary by product, currency and scenario.
    """

    def __init__(self, profile_provider: NonMaturityDepositProfileProvider) -> None:
        self._profile_provider = profile_provider

    def apply(
        self,
        *,
        position: BankingBookPosition,
        contractual_cashflows: tuple[IRRBBCashFlow, ...],
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        del contractual_cashflows
        self._validate_position(position)

        profile = self._profile_provider.profile_for(
            position=position,
            scenario=scenario,
            valuation_date=valuation_date,
        )
        if profile.scenario is not scenario:
            raise ValueError("NMD behavioral profile scenario does not match requested scenario")

        direction = (
            CashFlowDirection.PAYABLE
            if position.side is BankingBookSide.LIABILITY
            else CashFlowDirection.RECEIVABLE
        )
        flows: list[IRRBBCashFlow] = []
        for allocation in sorted(profile.allocations, key=lambda item: item.tenor_months):
            payment_date = self._add_months(valuation_date, allocation.tenor_months)
            flows.append(
                IRRBBCashFlow(
                    position_id=position.position_id,
                    side=position.side,
                    direction=direction,
                    amount=Money(
                        position.principal.amount * allocation.weight,
                        position.currency,
                    ),
                    cashflow_date=payment_date,
                    risk_date=payment_date,
                    flow_type="BEHAVIORAL_PRINCIPAL",
                    source_reference=position.source_reference,
                    amount_status=CashFlowAmountStatus.BEHAVIORAL,
                    projection_basis=(
                        f"{profile.methodology.code}:{profile.methodology.version}|"
                        f"{profile.source_reference}|TENOR_MONTHS={allocation.tenor_months}|"
                        f"SCENARIO={scenario.value}"
                    ),
                )
            )
        return tuple(flows)

    @staticmethod
    def _validate_position(position: BankingBookPosition) -> None:
        is_nmd = (
            position.instrument_class is IRRBBInstrumentClass.NON_MATURITY_DEPOSIT
            or position.payment_structure is PaymentStructure.NON_MATURITY
            or position.optionality is OptionalityType.NON_MATURITY_DEPOSIT
        )
        if not is_nmd:
            raise ValueError("NMD behavioral model requires a non-maturity-deposit position")
        if position.side is BankingBookSide.OFF_BALANCE:
            raise ValueError("NMD behavioral model does not support off-balance positions")

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        month_index = value.year * 12 + value.month - 1 + months
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(value.day, monthrange(year, month)[1])
        return date(year, month, day)
