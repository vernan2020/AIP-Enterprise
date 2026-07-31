from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.instruments.bonds.bond import Bond


@dataclass
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
