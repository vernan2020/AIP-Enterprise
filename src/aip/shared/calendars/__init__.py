"""Business calendars for AIP Enterprise.

This module defines interfaces and implementations for business calendars,
holiday providers, and weekend rules used in business day calculations.

Classes:
    BusinessCalendar: Interface for business day calculations.
    HolidayProvider: Interface for holiday definitions.
    WeekendRules: Weekend day definitions.
    CostaRicaCalendar: Costa Rica business calendar implementation.
"""

from abc import ABC, abstractmethod
from datetime import date, timedelta
from enum import Enum
from dataclasses import dataclass
from typing import Iterable, Mapping


class WeekendRules(Enum):
    """Weekend day definitions for different markets.
    
    References:
    - Market conventions for different regions
    """
    
    SATURDAY_SUNDAY = "SAT_SUN"
    """Saturday and Sunday (most Western markets)."""
    
    FRIDAY_SATURDAY = "FRI_SAT"
    """Friday and Saturday (Middle East and some Asian markets)."""
    
    FRIDAY_SATURDAY_SUNDAY = "FRI_SAT_SUN"
    """Friday, Saturday, Sunday (some regions)."""
    
    def is_weekend(self, day: date) -> bool:
        """Check if day is weekend.
        
        Args:
            day: The date to check.
            
        Returns:
            True if day is weekend, False otherwise.
        """
        # Python weekday: Monday=0, Tuesday=1, ..., Friday=4, Saturday=5, Sunday=6
        weekday = day.weekday()
        
        if self == WeekendRules.SATURDAY_SUNDAY:
            return weekday in (5, 6)
        elif self == WeekendRules.FRIDAY_SATURDAY:
            return weekday in (4, 5)
        elif self == WeekendRules.FRIDAY_SATURDAY_SUNDAY:
            return weekday in (4, 5, 6)
        
        raise ValueError(f"Unknown weekend rule: {self}")


class HolidayProvider(ABC):
    """Interface for providing holiday information.
    
    Implementations provide holiday calendars for specific regions or markets.
    """
    
    @abstractmethod
    def is_holiday(self, day: date) -> bool:
        """Check if date is a holiday.
        
        Args:
            day: The date to check.
            
        Returns:
            True if date is a holiday, False otherwise.
        """
    
    @abstractmethod
    def get_holidays(self, start: date, end: date) -> list[date]:
        """Get list of holidays in date range.
        
        Args:
            start: Start date (inclusive).
            end: End date (inclusive).
            
        Returns:
            List of holiday dates.
        """


class BusinessCalendar(ABC):
    """Interface for business calendar operations.
    
    Provides methods for business day calculations including:
    - Checking if date is business day
    - Finding next/previous business day
    - Calculating business days between dates
    """
    
    @abstractmethod
    def is_business_day(self, day: date) -> bool:
        """Check if date is a business day.
        
        Args:
            day: The date to check.
            
        Returns:
            True if date is a business day (not weekend or holiday).
        """
    
    @abstractmethod
    def next_business_day(self, start_date: date) -> date:
        """Find next business day.
        
        Args:
            start_date: The date to start from.
            
        Returns:
            The next business day (or start_date if already business day).
        """
    
    @abstractmethod
    def previous_business_day(self, start_date: date) -> date:
        """Find previous business day.
        
        Args:
            start_date: The date to start from.
            
        Returns:
            The previous business day.
        """
    
    @abstractmethod
    def business_days_between(self, start: date, end: date) -> int:
        """Calculate number of business days between dates.
        
        Args:
            start: Start date (inclusive).
            end: End date (inclusive).
            
        Returns:
            Number of business days between dates.
        """


@dataclass
class CostaRicaCalendar(BusinessCalendar):
    """Business calendar for Costa Rica.
    
    Implements Costa Rican business day calculations including:
    - Saturday-Sunday weekends
    - Official Costa Rican holidays
    
    Attributes:
        weekend_rules: Weekend definition (default: Saturday-Sunday).
        holiday_provider: Custom holiday provider (optional).
    """
    
    weekend_rules: WeekendRules = WeekendRules.SATURDAY_SUNDAY
    holiday_provider: HolidayProvider | None = None
    
    def __post_init__(self) -> None:
        """Initialize calendar."""
        if self.holiday_provider is None:
            self.holiday_provider = CostaRicaHolidayProvider()
    
    def is_business_day(self, day: date) -> bool:
        """Check if date is a business day in Costa Rica.
        
        Args:
            day: The date to check.
            
        Returns:
            True if date is business day (not weekend or holiday).
        """
        # Check if weekend
        if self.weekend_rules.is_weekend(day):
            return False
        
        # Check if holiday
        if self.holiday_provider and self.holiday_provider.is_holiday(day):
            return False
        
        return True
    
    def next_business_day(self, start_date: date) -> date:
        """Find next business day in Costa Rica.
        
        Args:
            start_date: The date to start from.
            
        Returns:
            The next business day after start_date.
        """
        current = start_date + timedelta(days=1)
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current
    
    def previous_business_day(self, start_date: date) -> date:
        """Find previous business day in Costa Rica.
        
        Args:
            start_date: The date to start from.
            
        Returns:
            The previous business day before start_date.
        """
        current = start_date - timedelta(days=1)
        while not self.is_business_day(current):
            current -= timedelta(days=1)
        return current
    
    def business_days_between(self, start: date, end: date) -> int:
        """Calculate business days between dates in Costa Rica.
        
        Args:
            start: Start date (inclusive).
            end: End date (inclusive).
            
        Returns:
            Number of business days.
        """
        count = 0
        current = start
        while current <= end:
            if self.is_business_day(current):
                count += 1
            current += timedelta(days=1)
        return count


class CostaRicaHolidayProvider(HolidayProvider):
    """Holiday provider for Costa Rica.

    This provider composes two independent sources:
    - Statutory national holidays
    - Optional institutional/banking holidays configurable by year

    August 2 (Our Lady of Los Angeles / Patrona) is NOT treated as a universal
    national banking holiday by default. If an institution observes it, it can be
    enabled via the institutional configuration.
    
    References:
    - Costa Rican Labor Code (Código de Trabajo)
    - Central Bank of Costa Rica (Banco Central)
    """

    def __init__(
        self,
        institutional_holidays_by_year: Mapping[int, Iterable[date]] | None = None,
        include_august_2_as_institutional: bool = False,
    ) -> None:
        """Initialize Costa Rica holiday provider.

        Args:
            institutional_holidays_by_year: Optional institutional holidays keyed
                by year. These do not modify statutory holidays.
            include_august_2_as_institutional: Whether to include August 2 as an
                institutional holiday in configured years or queried years.
        """
        self._statutory_provider = CostaRicaStatutoryHolidayProvider()
        self._institutional_provider = InstitutionalHolidayProvider(
            holidays_by_year=institutional_holidays_by_year,
            include_august_2=include_august_2_as_institutional,
        )
    
    def is_holiday(self, day: date) -> bool:
        """Check if date is holiday in Costa Rica profile.
        
        Args:
            day: The date to check.
            
        Returns:
            True if date is statutory or configured institutional holiday.
        """
        return self._statutory_provider.is_holiday(day) or self._institutional_provider.is_holiday(day)
    
    def get_holidays(self, start: date, end: date) -> list[date]:
        """Get holidays in date range for this profile.
        
        Args:
            start: Start date.
            end: End date.
            
        Returns:
            List of holiday dates.
        """
        holidays: list[date] = []
        current = start

        while current <= end:
            if self.is_holiday(current):
                holidays.append(current)
            current += timedelta(days=1)

        return holidays

    def get_statutory_holidays(self, year: int) -> set[date]:
        """Get statutory national holidays for a specific year."""
        return self._statutory_provider.get_holidays_for_year(year)

    def get_institutional_holidays(self, year: int) -> set[date]:
        """Get configured institutional holidays for a specific year."""
        return self._institutional_provider.get_holidays_for_year(year)


class CostaRicaStatutoryHolidayProvider(HolidayProvider):
    """Statutory national holidays for Costa Rica.

    This provider contains national holidays only. It intentionally excludes
    institution-specific banking closures.
    """

    # Statutory fixed holidays (month, day).
    FIXED_HOLIDAYS = [
        (1, 1),   # New Year's Day
        (4, 11),  # Juan Santamaría Day
        (5, 1),   # Labor Day
        (7, 25),  # Annexation of Guanacaste
        (9, 15),  # Independence Day
        (10, 12), # Columbus Day / Día del Descubrimiento
        (12, 25), # Christmas Day
    ]

    def is_holiday(self, day: date) -> bool:
        """Check if date is a statutory national holiday."""
        for month, day_of_month in self.FIXED_HOLIDAYS:
            if day.month == month and day.day == day_of_month:
                return True

        return self._is_easter_holiday(day)

    def get_holidays(self, start: date, end: date) -> list[date]:
        """Get statutory holidays in an inclusive date range."""
        holidays: list[date] = []
        current = start

        while current <= end:
            if self.is_holiday(current):
                holidays.append(current)
            current += timedelta(days=1)

        return holidays

    def get_holidays_for_year(self, year: int) -> set[date]:
        """Get statutory national holidays for a specific year."""
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        return set(self.get_holidays(start, end))
    
    def _is_easter_holiday(self, day: date) -> bool:
        """Check if date is Easter-related holiday.
        
        Costa Rica observes:
        - Holy Thursday (Jueves Santo) - 3 days before Easter
        - Good Friday (Viernes Santo) - 2 days before Easter
        - Black Monday (Lunes Negro) - 1 day before Easter
        """
        year = day.year
        easter_date = self._calculate_easter(year)
        
        # Check Easter-related holidays (3 days before to day before Easter)
        for days_before in [3, 2, 1]:
            holiday_date = easter_date - timedelta(days=days_before)
            if day == holiday_date:
                return True
        
        return False
    
    @staticmethod
    def _calculate_easter(year: int) -> date:
        """Calculate Easter Sunday for given year.
        
        Uses the Computus algorithm (Anonymous Gregorian algorithm).
        
        Args:
            year: The year to calculate Easter for.
            
        Returns:
            Easter Sunday date.
        """
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        
        return date(year, month, day)


class InstitutionalHolidayProvider(HolidayProvider):
    """Configurable institutional holiday provider.

    Holidays are configured per year and can represent institution-specific
    banking closures without modifying national statutory holidays.
    """

    AUGUST_2 = (8, 2)

    def __init__(
        self,
        holidays_by_year: Mapping[int, Iterable[date]] | None = None,
        include_august_2: bool = False,
    ) -> None:
        """Initialize institutional holiday provider.

        Args:
            holidays_by_year: Institutional holidays keyed by year.
            include_august_2: Whether to include August 2 as an institutional
                holiday in years where holidays are queried.
        """
        self._holidays_by_year: dict[int, set[date]] = {}
        if holidays_by_year:
            for year, days in holidays_by_year.items():
                self._holidays_by_year[year] = set(days)

        self._include_august_2 = include_august_2

    def is_holiday(self, day: date) -> bool:
        """Check if date is an institutional holiday."""
        year_holidays = self.get_holidays_for_year(day.year)
        return day in year_holidays

    def get_holidays(self, start: date, end: date) -> list[date]:
        """Get institutional holidays in an inclusive date range."""
        holidays: list[date] = []
        current = start

        while current <= end:
            if self.is_holiday(current):
                holidays.append(current)
            current += timedelta(days=1)

        return holidays

    def get_holidays_for_year(self, year: int) -> set[date]:
        """Get institutional holidays for a specific year."""
        holidays = set(self._holidays_by_year.get(year, set()))

        if self._include_august_2:
            holidays.add(date(year, self.AUGUST_2[0], self.AUGUST_2[1]))

        return holidays
