"""Financial conventions for AIP Enterprise.

This module provides standard financial conventions for day counting,
frequencies, coupon schedules, and business day adjustments.

Classes:
    DayCountConvention: Day counting convention enumeration.
    Frequency: Payment/coupon frequency enumeration.
    CouponConvention: Coupon payment conventions.
    BusinessDayConvention: Business day adjustment enumeration.
"""

from enum import Enum
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, timedelta
from typing import Callable


class DayCountConvention(Enum):
    """Day count conventions for interest calculations.
    
    References:
    - ISDA Day Count Conventions
    - FINRA Rule 4512
    """
    
    ACTUAL_365 = "ACTUAL/365"
    """Actual days / 365 days per year. Most common for corporate bonds."""
    
    ACTUAL_360 = "ACTUAL/360"
    """Actual days / 360 days per year. Common for floating rate notes."""
    
    ACTUAL_ACTUAL = "ACTUAL/ACTUAL"
    """Actual days / actual days in year. Used for Treasury bonds."""
    
    THIRTY_360 = "30/360"
    """Assumes 30 days per month, 360 days per year."""
    
    THIRTY_E_360 = "30E/360"
    """European version of 30/360."""
    
    def calculate_year_fraction(self, start: date, end: date) -> Decimal:
        """Calculate year fraction between two dates.
        
        Args:
            start: Start date.
            end: End date.
            
        Returns:
            Fraction of year between dates.
        """
        actual_days = (end - start).days
        
        if self == DayCountConvention.ACTUAL_365:
            return Decimal(actual_days) / Decimal(365)
        
        elif self == DayCountConvention.ACTUAL_360:
            return Decimal(actual_days) / Decimal(360)
        
        elif self == DayCountConvention.ACTUAL_ACTUAL:
            # Get number of leap days in period
            leap_days = self._count_leap_days(start, end)
            year_start = start.year
            year_end = end.year
            
            if year_start == year_end:
                days_in_year = 366 if self._is_leap_year(year_start) else 365
                return Decimal(actual_days) / Decimal(days_in_year)
            
            return Decimal(actual_days) / (Decimal(365) + Decimal(leap_days) / Decimal(actual_days))
        
        elif self == DayCountConvention.THIRTY_360:
            return Decimal(self._days_30_360(start, end)) / Decimal(360)
        
        elif self == DayCountConvention.THIRTY_E_360:
            return Decimal(self._days_30e_360(start, end)) / Decimal(360)
        
        raise ValueError(f"Unknown day count convention: {self}")
    
    @staticmethod
    def _is_leap_year(year: int) -> bool:
        """Check if year is leap year."""
        return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    
    @staticmethod
    def _count_leap_days(start: date, end: date) -> int:
        """Count leap days between two dates."""
        count = 0
        current = start
        while current <= end:
            if DayCountConvention._is_leap_year(current.year):
                count += 1
            current = date(current.year + 1, 1, 1)
        return count
    
    @staticmethod
    def _days_30_360(start: date, end: date) -> int:
        """Calculate days using 30/360 convention."""
        d1 = min(start.day, 30)
        d2 = min(end.day, 30) if d1 == 30 else end.day
        
        days = 360 * (end.year - start.year)
        days += 30 * (end.month - start.month)
        days += d2 - d1
        
        return days
    
    @staticmethod
    def _days_30e_360(start: date, end: date) -> int:
        """Calculate days using 30E/360 convention."""
        d1 = min(start.day, 30)
        d2 = min(end.day, 30)
        
        days = 360 * (end.year - start.year)
        days += 30 * (end.month - start.month)
        days += d2 - d1
        
        return days


class Frequency(Enum):
    """Payment frequency for bonds and floating rate notes.
    
    References:
    - ISDA Rate Fixing Conventions
    - Fixed Income Securities Standards
    """
    
    ANNUAL = 1
    """Annual payments (every 12 months)."""
    
    SEMI_ANNUAL = 2
    """Semi-annual payments (every 6 months)."""
    
    QUARTERLY = 4
    """Quarterly payments (every 3 months)."""
    
    MONTHLY = 12
    """Monthly payments."""
    
    def months_between_payments(self) -> int:
        """Get months between payments.
        
        Returns:
            Number of months between payments.
        """
        return 12 // self.value
    
    def days_between_payments(self) -> int:
        """Get approximate days between payments.
        
        Returns:
            Approximate number of days (30 days per month).
        """
        return self.months_between_payments() * 30


@dataclass(frozen=True)
class CouponConvention:
    """Coupon payment convention for fixed income securities.
    
    Attributes:
        frequency: Payment frequency.
        day_count: Day count convention.
        basis_month: Month when coupon period starts (1-12).
        basis_day: Day when coupon period starts (1-31).
    """
    
    frequency: Frequency
    day_count: DayCountConvention
    basis_month: int
    basis_day: int
    
    def __post_init__(self) -> None:
        """Validate coupon convention."""
        if not (1 <= self.basis_month <= 12):
            raise ValueError("basis_month must be between 1 and 12")
        if not (1 <= self.basis_day <= 31):
            raise ValueError("basis_day must be between 1 and 31")
    
    def next_coupon_date(self, from_date: date) -> date:
        """Calculate next coupon payment date.
        
        Args:
            from_date: The date to calculate from.
            
        Returns:
            The next coupon payment date.
        """
        months_between = self.frequency.months_between_payments()
        month = self.basis_month
        year = from_date.year
        
        # Advance to next coupon month
        while True:
            coupon_date = date(year, month, min(self.basis_day, 28))
            if coupon_date > from_date:
                return coupon_date
            
            month += months_between
            if month > 12:
                month -= 12
                year += 1
    
    def previous_coupon_date(self, from_date: date) -> date:
        """Calculate previous coupon payment date.
        
        Args:
            from_date: The date to calculate from.
            
        Returns:
            The previous coupon payment date.
        """
        months_between = self.frequency.months_between_payments()
        month = self.basis_month
        year = from_date.year
        
        # Go backward to previous coupon month
        while True:
            coupon_date = date(year, month, min(self.basis_day, 28))
            if coupon_date < from_date:
                return coupon_date
            
            month -= months_between
            if month < 1:
                month += 12
                year -= 1


class BusinessDayConvention(Enum):
    """Business day adjustment convention.
    
    References:
    - ISDA Definitions
    - Market Conventions for Date Adjustments
    """
    
    FOLLOWING = "Following"
    """Adjust to next business day if not a business day."""
    
    MODIFIED_FOLLOWING = "ModifiedFollowing"
    """Adjust to next business day unless it falls in next month."""
    
    PRECEDING = "Preceding"
    """Adjust to previous business day if not a business day."""
    
    MODIFIED_PRECEDING = "ModifiedPreceding"
    """Adjust to previous business day unless it falls in previous month."""
    
    UNADJUSTED = "Unadjusted"
    """Do not adjust date."""
    
    def adjust(self, target_date: date, is_business_day: Callable[[date], bool]) -> date:
        """Adjust date according to convention.
        
        Args:
            target_date: The date to adjust.
            is_business_day: Function that returns True if date is business day.
            
        Returns:
            The adjusted date.
        """
        if is_business_day(target_date):
            return target_date
        
        if self == BusinessDayConvention.UNADJUSTED:
            return target_date
        
        elif self == BusinessDayConvention.FOLLOWING:
            current = target_date
            while not is_business_day(current):
                current += timedelta(days=1)
            return current
        
        elif self == BusinessDayConvention.PRECEDING:
            current = target_date
            while not is_business_day(current):
                current -= timedelta(days=1)
            return current
        
        elif self == BusinessDayConvention.MODIFIED_FOLLOWING:
            current = target_date
            while not is_business_day(current):
                current += timedelta(days=1)
            
            # If moved to next month, go back to previous business day
            if current.month != target_date.month:
                current = target_date
                while not is_business_day(current):
                    current -= timedelta(days=1)
            
            return current
        
        elif self == BusinessDayConvention.MODIFIED_PRECEDING:
            current = target_date
            while not is_business_day(current):
                current -= timedelta(days=1)
            
            # If moved to previous month, go forward to next business day
            if current.month != target_date.month:
                current = target_date
                while not is_business_day(current):
                    current += timedelta(days=1)
            
            return current
        
        raise ValueError(f"Unknown convention: {self}")
