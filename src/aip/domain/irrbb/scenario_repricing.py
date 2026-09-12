from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.shared.money import Money


@dataclass(frozen=True, slots=True)
class FloatingRateCouponBasis:
    """Auditable basis required to reproject one floating-rate interest cash flow.

    Rates use decimal form (for example ``Decimal("0.05")`` means 5%). The
    ``accrual_fraction`` must already reflect the approved day-count convention;
    this domain object deliberately does not infer ACT/360, ACT/365 or 30/360.
    """

    position_id: str
    cashflow_date: date
    reset_date: date
    reference_rate_code: str
    notional: Money
    accrual_fraction: Decimal
    spread: Decimal
    source_reference: str
    rate_floor: Decimal | None = None
    rate_cap: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("floating coupon basis position_id is required")
        if not self.reference_rate_code.strip():
            raise ValueError("floating coupon basis reference_rate_code is required")
        if not self.source_reference.strip():
            raise ValueError("floating coupon basis source_reference is required")
        if self.notional.amount < 0:
            raise ValueError("floating coupon basis notional cannot be negative")
        if self.accrual_fraction <= 0:
            raise ValueError("floating coupon basis accrual_fraction must be positive")
        if self.reset_date > self.cashflow_date:
            raise ValueError("floating coupon reset_date cannot be after cashflow_date")
        if (
            self.rate_floor is not None
            and self.rate_cap is not None
            and self.rate_floor > self.rate_cap
        ):
            raise ValueError("floating coupon rate_floor cannot exceed rate_cap")

    def effective_rate(self, reference_rate: Decimal) -> Decimal:
        """Return reference plus spread after contractual floor/cap constraints."""

        rate = reference_rate + self.spread
        if self.rate_floor is not None:
            rate = max(rate, self.rate_floor)
        if self.rate_cap is not None:
            rate = min(rate, self.rate_cap)
        return rate
