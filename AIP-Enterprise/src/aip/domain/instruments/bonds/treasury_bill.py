from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.instruments.bonds.bond import Bond
from aip.domain.instruments.exceptions import InstrumentValidationError


@dataclass(slots=True)
class TreasuryBill(Bond):
    """Short-term zero-coupon Treasury bill."""

    discount_rate: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        from aip.domain.instruments.base.fixed_income_instrument import FixedIncomeInstrument

        FixedIncomeInstrument.__post_init__(self)
        self.discount_rate = self._ensure_decimal(self.discount_rate)
        if self.discount_rate < 0:
            raise InstrumentValidationError("Discount rate cannot be negative")

    def calculate_price(self) -> Decimal:
        if self.maturity_date <= self.issue_date:
            return self.face_value
        days = (self.maturity_date - self.issue_date).days
        year_fraction = Decimal(days) / Decimal(360)
        discount_factor = Decimal("1") - (self.discount_rate * year_fraction)
        return self.face_value * discount_factor

    def calculate_yield(self) -> Decimal:
        if self.clean_price <= 0:
            return Decimal("0")
        return (self.face_value / self.clean_price - Decimal("1")) * Decimal("100")
