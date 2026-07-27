from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.instruments.bonds.bond import Bond
from aip.domain.instruments.enums.amortization_type import AmortizationType
from aip.domain.instruments.enums.coupon_type import CouponType
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule
from aip.shared.conventions import DayCountConvention


@dataclass(slots=True)
class GovernmentBond(Bond):
    """Government-issued bond, including Costa Rica sovereign bonds."""

    jurisdiction: str = "CR"

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.issuer.name.lower().find("costa") == -1 and self.issuer.name.lower().find("government") == -1:
            self.metadata["jurisdiction"] = self.jurisdiction

    def calculate_price(self) -> Decimal:
        schedule = self.generate_schedule()
        if not schedule.coupons:
            return self.face_value
        price = Decimal("0")
        for coupon in schedule.coupons:
            price += coupon.amount / (Decimal("1") + self.yield_rate)
        return price + self.face_value / (Decimal("1") + self.yield_rate)
