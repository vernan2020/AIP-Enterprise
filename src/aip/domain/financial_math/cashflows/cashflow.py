from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.financial_math.exceptions import InvalidCashFlowError


@dataclass(frozen=True, slots=True)
class CashFlow:
    """Immutable single cash flow."""

    payment_date: date
    amount: Decimal
    currency: str
    cash_flow_type: str = "coupon"
    source_reference: str | None = None

    def __post_init__(self) -> None:
        if self.payment_date is None:
            raise InvalidCashFlowError("Payment date must be provided")
        if not self.currency or not self.currency.strip():
            raise InvalidCashFlowError("Currency must be provided")
        if self.amount == 0:
            raise InvalidCashFlowError("Cash flow amount cannot be zero")
