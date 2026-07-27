from __future__ import annotations

from enum import Enum
from decimal import Decimal
from datetime import date


class DayCountConvention(Enum):
    """Supported day-count conventions."""

    ACTUAL_365 = "ACTUAL/365"
    ACTUAL_360 = "ACTUAL/360"
    THIRTY_360 = "30/360"

    def calculate_year_fraction(self, start: date, end: date) -> Decimal:
        if self == DayCountConvention.ACTUAL_360:
            return Decimal((end - start).days) / Decimal("360")
        if self == DayCountConvention.THIRTY_360:
            return Decimal("360") / Decimal("360")
        return Decimal((end - start).days) / Decimal("365")


class BusinessDayConvention(Enum):
    """Simple business-day convention placeholder."""

    FOLLOWING = "Following"
    PRECEDING = "Preceding"
    UNADJUSTED = "Unadjusted"
