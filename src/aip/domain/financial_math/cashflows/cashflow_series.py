from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable, Iterable

from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.financial_math.exceptions import CurrencyMismatchError, InvalidCashFlowError


@dataclass(frozen=True, slots=True)
class CashFlowSeries:
    """Immutable series of cash flows with aggregation and valuation helpers."""

    cash_flows: tuple[CashFlow, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.cash_flows:
            raise InvalidCashFlowError("Cash flow series cannot be empty")
        self.validate_currency_consistency()

    @classmethod
    def from_cashflows(cls, cash_flows: Iterable[CashFlow]) -> "CashFlowSeries":
        ordered = tuple(sorted(cash_flows, key=lambda item: item.payment_date))
        instance = cls.__new__(cls)
        object.__setattr__(instance, "cash_flows", ordered)
        return instance

    def order_chronologically(self) -> list[CashFlow]:
        return list(self.cash_flows)

    def aggregate_duplicates(
        self,
        *,
        fx_conversion: Callable[[str, str, Decimal], Decimal] | None = None,
    ) -> "CashFlowSeries":
        currencies = {cash_flow.currency for cash_flow in self.cash_flows}
        if len(currencies) > 1 and fx_conversion is None:
            raise CurrencyMismatchError("Cash flow series contains mixed currencies")
        grouped: dict[date, Decimal] = {}
        for cash_flow in self.cash_flows:
            amount = cash_flow.amount
            if fx_conversion is not None and len(currencies) > 1:
                amount = fx_conversion(cash_flow.currency, next(iter(currencies)), cash_flow.amount)
            grouped[cash_flow.payment_date] = grouped.get(cash_flow.payment_date, Decimal("0")) + amount
        aggregated = tuple(
            CashFlow(payment_date=payment_date, amount=amount, currency=next(iter(currencies)), cash_flow_type="coupon")
            for payment_date, amount in sorted(grouped.items())
        )
        return CashFlowSeries(cash_flows=aggregated)

    def filter_by_date_range(self, start: date, end: date) -> "CashFlowSeries":
        filtered = tuple(cash_flow for cash_flow in self.cash_flows if start <= cash_flow.payment_date <= end)
        return CashFlowSeries(cash_flows=filtered)

    def total_amount(self) -> Decimal:
        return sum((cash_flow.amount for cash_flow in self.cash_flows), Decimal("0"))

    def validate_currency_consistency(self) -> None:
        currencies = {cash_flow.currency for cash_flow in self.cash_flows}
        if len(currencies) > 1:
            raise CurrencyMismatchError("Cash flow series contains mixed currencies")

    def present_value(
        self,
        rate: Decimal,
        *,
        valuation_date: date | None = None,
        compounding: str = "annual",
        frequency: int = 1,
    ) -> Decimal:
        from aip.domain.financial_math.discounting.present_value import present_value_series

        return present_value_series(self, rate, valuation_date=valuation_date, compounding=compounding, frequency=frequency)
