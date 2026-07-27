"""Business date operations for AIP Enterprise.

This module provides value objects and utilities for business date operations,
including business dates, date ranges, and business day calculations.

Classes:
    BusinessDate: Immutable business date value object.
    BusinessPeriod: Immutable period between two dates.
    DateRange: Date range with business day support.
    BusinessDayCalculator: Utility for business day calculations.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Self, Sequence

from aip.shared.validation import Guard
from aip.shared.calendars import BusinessCalendar, CostaRicaCalendar
from aip.shared.conventions import BusinessDayConvention


@dataclass(frozen=True)
class BusinessDate:
    """Immutable business date value object.
    
    Represents a date with business day adjustment support.
    
    Attributes:
        date: The calendar date.
        calendar: Business calendar for adjustments.
    """
    
    date: date
    calendar: BusinessCalendar
    
    def __post_init__(self) -> None:
        """Validate initialization."""
        Guard.required(self.date, "date")
        Guard.required(self.calendar, "calendar")
    
    def __str__(self) -> str:
        """String representation."""
        return self.date.isoformat()
    
    def __lt__(self, other: Self) -> bool:
        """Less than comparison."""
        return self.date < other.date
    
    def __le__(self, other: Self) -> bool:
        """Less than or equal comparison."""
        return self.date <= other.date
    
    def __gt__(self, other: Self) -> bool:
        """Greater than comparison."""
        return self.date > other.date
    
    def __ge__(self, other: Self) -> bool:
        """Greater than or equal comparison."""
        return self.date >= other.date
    
    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if not isinstance(other, BusinessDate):
            return False
        return self.date == other.date
    
    def __hash__(self) -> int:
        """Hash for use in collections."""
        return hash(self.date)
    
    def is_business_day(self) -> bool:
        """Check if this date is a business day.
        
        Returns:
            True if date is a business day.
        """
        return self.calendar.is_business_day(self.date)
    
    def next_business_day(self) -> Self:
        """Get next business day.
        
        Returns:
            New BusinessDate for next business day.
        """
        next_date = self.calendar.next_business_day(self.date)
        return BusinessDate(next_date, self.calendar)
    
    def previous_business_day(self) -> Self:
        """Get previous business day.
        
        Returns:
            New BusinessDate for previous business day.
        """
        prev_date = self.calendar.previous_business_day(self.date)
        return BusinessDate(prev_date, self.calendar)
    
    def add_days(self, days: int) -> Self:
        """Add calendar days.
        
        Args:
            days: Number of days to add.
            
        Returns:
            New BusinessDate after adding days.
        """
        new_date = self.date + timedelta(days=days)
        return BusinessDate(new_date, self.calendar)
    
    def add_business_days(self, business_days: int) -> Self:
        """Add business days.
        
        Args:
            business_days: Number of business days to add.
            
        Returns:
            New BusinessDate after adding business days.
        """
        current = self.date
        days_added = 0
        direction = 1 if business_days > 0 else -1
        
        while abs(days_added) < abs(business_days):
            current += timedelta(days=direction)
            if self.calendar.is_business_day(current):
                days_added += direction
        
        return BusinessDate(current, self.calendar)
    
    def adjust(self, convention: BusinessDayConvention) -> Self:
        """Adjust date according to convention.
        
        Args:
            convention: Business day adjustment convention.
            
        Returns:
            New BusinessDate after adjustment.
        """
        adjusted = convention.adjust(self.date, self.calendar.is_business_day)
        return BusinessDate(adjusted, self.calendar)


@dataclass(frozen=True)
class BusinessPeriod:
    """Immutable period between two dates.
    
    Represents a period with support for business day calculations.
    
    Attributes:
        start: Start date.
        end: End date.
        calendar: Business calendar for calculations.
    """
    
    start: date
    end: date
    calendar: BusinessCalendar
    
    def __post_init__(self) -> None:
        """Validate initialization."""
        Guard.required(self.start, "start")
        Guard.required(self.end, "end")
        Guard.required(self.calendar, "calendar")
        
        if self.end < self.start:
            raise ValueError("End date must be after start date")
    
    def __str__(self) -> str:
        """String representation."""
        return f"{self.start.isoformat()} to {self.end.isoformat()}"
    
    def __len__(self) -> int:
        """Get calendar days in period."""
        return (self.end - self.start).days + 1
    
    def calendar_days(self) -> int:
        """Get number of calendar days in period.
        
        Returns:
            Number of calendar days (inclusive).
        """
        return (self.end - self.start).days + 1
    
    def business_days(self) -> int:
        """Get number of business days in period.
        
        Returns:
            Number of business days (inclusive).
        """
        return self.calendar.business_days_between(self.start, self.end)
    
    def contains(self, day: date) -> bool:
        """Check if date is within period.
        
        Args:
            day: The date to check.
            
        Returns:
            True if date is within period (inclusive).
        """
        return self.start <= day <= self.end
    
    def overlap(self, other: Self) -> Self | None:
        """Calculate overlap with another period.
        
        Args:
            other: The other period.
            
        Returns:
            New period representing overlap, or None if no overlap.
        """
        overlap_start = max(self.start, other.start)
        overlap_end = min(self.end, other.end)
        
        if overlap_start <= overlap_end:
            return BusinessPeriod(overlap_start, overlap_end, self.calendar)
        
        return None


@dataclass(frozen=True)
class DateRange:
    """Immutable date range with business day support.
    
    Provides methods for iterating and analyzing date ranges.
    
    Attributes:
        start: Start date.
        end: End date.
        calendar: Business calendar for calculations.
    """
    
    start: date
    end: date
    calendar: BusinessCalendar
    
    def __post_init__(self) -> None:
        """Validate initialization."""
        Guard.required(self.start, "start")
        Guard.required(self.end, "end")
        Guard.required(self.calendar, "calendar")
        
        if self.end < self.start:
            raise ValueError("End date must be after start date")
    
    def __str__(self) -> str:
        """String representation."""
        return f"{self.start.isoformat()}/{self.end.isoformat()}"
    
    def __len__(self) -> int:
        """Get calendar days in range."""
        return (self.end - self.start).days + 1
    
    def __iter__(self):
        """Iterate over calendar days in range."""
        current = self.start
        while current <= self.end:
            yield current
            current += timedelta(days=1)
    
    def calendar_days(self) -> Sequence[date]:
        """Get all calendar days in range.
        
        Returns:
            List of all dates in range.
        """
        return list(self)
    
    def business_days(self) -> Sequence[date]:
        """Get all business days in range.
        
        Returns:
            List of business dates in range.
        """
        return [d for d in self if self.calendar.is_business_day(d)]


class BusinessDayCalculator:
    """Utility for business day calculations.
    
    Provides static methods for common business day operations.
    """
    
    @staticmethod
    def days_between(
        start: date,
        end: date,
        calendar: BusinessCalendar,
    ) -> int:
        """Calculate calendar days between dates.
        
        Args:
            start: Start date.
            end: End date.
            calendar: Business calendar.
            
        Returns:
            Number of calendar days.
        """
        return (end - start).days
    
    @staticmethod
    def business_days_between(
        start: date,
        end: date,
        calendar: BusinessCalendar,
    ) -> int:
        """Calculate business days between dates.
        
        Args:
            start: Start date.
            end: End date.
            calendar: Business calendar.
            
        Returns:
            Number of business days.
        """
        return calendar.business_days_between(start, end)
    
    @staticmethod
    def add_business_days(
        start_date: date,
        num_days: int,
        calendar: BusinessCalendar,
    ) -> date:
        """Add business days to date.
        
        Args:
            start_date: Starting date.
            num_days: Number of business days to add.
            calendar: Business calendar.
            
        Returns:
            Result date.
        """
        business_date = BusinessDate(start_date, calendar)
        result = business_date.add_business_days(num_days)
        return result.date
    
    @staticmethod
    def next_business_day(
        start_date: date,
        calendar: BusinessCalendar,
    ) -> date:
        """Find next business day.
        
        Args:
            start_date: Starting date.
            calendar: Business calendar.
            
        Returns:
            Next business day.
        """
        return calendar.next_business_day(start_date)
    
    @staticmethod
    def previous_business_day(
        start_date: date,
        calendar: BusinessCalendar,
    ) -> date:
        """Find previous business day.
        
        Args:
            start_date: Starting date.
            calendar: Business calendar.
            
        Returns:
            Previous business day.
        """
        return calendar.previous_business_day(start_date)
