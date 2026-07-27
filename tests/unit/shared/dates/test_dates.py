"""Tests for dates module.

Comprehensive tests for BusinessDate, BusinessPeriod, DateRange, and BusinessDayCalculator.
"""

import pytest
from datetime import date, timedelta

from src.aip.shared.dates import (
    BusinessDate,
    BusinessPeriod,
    DateRange,
    BusinessDayCalculator,
)
from src.aip.shared.calendars import CostaRicaCalendar
from src.aip.shared.conventions import BusinessDayConvention


class TestBusinessDate:
    """Tests for BusinessDate value object."""
    
    @pytest.fixture
    def calendar(self) -> CostaRicaCalendar:
        """Create test calendar."""
        return CostaRicaCalendar()
    
    def test_business_date_creation(self, calendar: CostaRicaCalendar) -> None:
        """Test BusinessDate can be created."""
        bd = BusinessDate(date(2024, 7, 29), calendar)
        assert bd.date == date(2024, 7, 29)
        assert bd.calendar == calendar
    
    def test_business_date_string_representation(self, calendar: CostaRicaCalendar) -> None:
        """Test string representation."""
        bd = BusinessDate(date(2024, 7, 29), calendar)
        assert str(bd) == "2024-07-29"
    
    def test_business_date_comparisons(self, calendar: CostaRicaCalendar) -> None:
        """Test comparison operations."""
        bd1 = BusinessDate(date(2024, 7, 29), calendar)
        bd2 = BusinessDate(date(2024, 7, 30), calendar)
        
        assert bd1 < bd2
        assert bd1 <= bd2
        assert bd2 > bd1
        assert bd2 >= bd1
    
    def test_business_date_equality(self, calendar: CostaRicaCalendar) -> None:
        """Test equality comparison."""
        bd1 = BusinessDate(date(2024, 7, 29), calendar)
        bd2 = BusinessDate(date(2024, 7, 29), calendar)
        bd3 = BusinessDate(date(2024, 7, 30), calendar)
        
        assert bd1 == bd2
        assert bd1 != bd3
    
    def test_business_date_hash(self, calendar: CostaRicaCalendar) -> None:
        """Test BusinessDate can be hashed."""
        bd1 = BusinessDate(date(2024, 7, 29), calendar)
        bd2 = BusinessDate(date(2024, 7, 29), calendar)
        
        assert hash(bd1) == hash(bd2)
    
    def test_is_business_day(self, calendar: CostaRicaCalendar) -> None:
        """Test is_business_day checks calendar."""
        # 2024-07-29 is Monday
        bd_monday = BusinessDate(date(2024, 7, 29), calendar)
        assert bd_monday.is_business_day() is True
        
        # 2024-07-27 is Saturday
        bd_saturday = BusinessDate(date(2024, 7, 27), calendar)
        assert bd_saturday.is_business_day() is False
    
    def test_next_business_day(self, calendar: CostaRicaCalendar) -> None:
        """Test next_business_day calculation."""
        # 2024-07-26 is Friday
        bd = BusinessDate(date(2024, 7, 26), calendar)
        next_bd = bd.next_business_day()
        
        assert next_bd.date.weekday() == 0  # Monday
    
    def test_previous_business_day(self, calendar: CostaRicaCalendar) -> None:
        """Test previous_business_day calculation."""
        # 2024-07-29 is Monday
        bd = BusinessDate(date(2024, 7, 29), calendar)
        prev_bd = bd.previous_business_day()
        
        assert prev_bd.date.weekday() == 4  # Friday
    
    def test_add_days(self, calendar: CostaRicaCalendar) -> None:
        """Test add_days method."""
        bd = BusinessDate(date(2024, 7, 29), calendar)
        result = bd.add_days(5)
        
        assert result.date == date(2024, 8, 3)
    
    def test_add_business_days(self, calendar: CostaRicaCalendar) -> None:
        """Test add_business_days method."""
        # 2024-07-29 is Monday
        bd = BusinessDate(date(2024, 7, 29), calendar)
        result = bd.add_business_days(4)

        # 4 business days from Monday: Tue, Wed, Thu, Fri
        assert result.date == date(2024, 8, 2)
    
    def test_adjust_with_convention(self, calendar: CostaRicaCalendar) -> None:
        """Test adjust method with convention."""
        # 2024-07-27 is Saturday
        bd = BusinessDate(date(2024, 7, 27), calendar)
        result = bd.adjust(BusinessDayConvention.FOLLOWING)
        
        assert result.date.weekday() == 0  # Monday


class TestBusinessPeriod:
    """Tests for BusinessPeriod."""
    
    @pytest.fixture
    def calendar(self) -> CostaRicaCalendar:
        """Create test calendar."""
        return CostaRicaCalendar()
    
    def test_business_period_creation(self, calendar: CostaRicaCalendar) -> None:
        """Test BusinessPeriod can be created."""
        start = date(2024, 7, 29)
        end = date(2024, 8, 2)
        period = BusinessPeriod(start, end, calendar)
        
        assert period.start == start
        assert period.end == end
    
    def test_business_period_calendar_days(self, calendar: CostaRicaCalendar) -> None:
        """Test calendar_days calculation."""
        start = date(2024, 7, 29)  # Monday
        end = date(2024, 8, 2)     # Friday
        period = BusinessPeriod(start, end, calendar)
        
        assert period.calendar_days() == 5
    
    def test_business_period_business_days(self, calendar: CostaRicaCalendar) -> None:
        """Test business_days calculation."""
        start = date(2024, 7, 29)  # Monday
        end = date(2024, 8, 6)     # Tuesday next week
        period = BusinessPeriod(start, end, calendar)

        # Mon, Tue, Wed, Thu, Fri, Mon, Tue
        assert period.business_days() == 7
    
    def test_business_period_contains(self, calendar: CostaRicaCalendar) -> None:
        """Test contains method."""
        start = date(2024, 7, 29)
        end = date(2024, 8, 2)
        period = BusinessPeriod(start, end, calendar)
        
        assert period.contains(date(2024, 7, 31)) is True
        assert period.contains(date(2024, 8, 5)) is False
    
    def test_business_period_overlap(self, calendar: CostaRicaCalendar) -> None:
        """Test overlap calculation."""
        period1 = BusinessPeriod(date(2024, 7, 29), date(2024, 8, 2), calendar)
        period2 = BusinessPeriod(date(2024, 7, 31), date(2024, 8, 5), calendar)
        
        overlap = period1.overlap(period2)
        assert overlap is not None
        assert overlap.start == date(2024, 7, 31)
        assert overlap.end == date(2024, 8, 2)
    
    def test_business_period_no_overlap(self, calendar: CostaRicaCalendar) -> None:
        """Test no overlap returns None."""
        period1 = BusinessPeriod(date(2024, 7, 29), date(2024, 7, 30), calendar)
        period2 = BusinessPeriod(date(2024, 8, 1), date(2024, 8, 2), calendar)
        
        overlap = period1.overlap(period2)
        assert overlap is None
    
    def test_business_period_invalid_end_raises_error(self, calendar: CostaRicaCalendar) -> None:
        """Test end before start raises error."""
        with pytest.raises(ValueError):
            BusinessPeriod(date(2024, 8, 2), date(2024, 7, 29), calendar)


class TestDateRange:
    """Tests for DateRange."""
    
    @pytest.fixture
    def calendar(self) -> CostaRicaCalendar:
        """Create test calendar."""
        return CostaRicaCalendar()
    
    def test_date_range_creation(self, calendar: CostaRicaCalendar) -> None:
        """Test DateRange can be created."""
        start = date(2024, 7, 29)
        end = date(2024, 8, 2)
        dr = DateRange(start, end, calendar)
        
        assert dr.start == start
        assert dr.end == end
    
    def test_date_range_length(self, calendar: CostaRicaCalendar) -> None:
        """Test length calculation."""
        start = date(2024, 7, 29)  # 5 days
        end = date(2024, 8, 2)
        dr = DateRange(start, end, calendar)
        
        assert len(dr) == 5
    
    def test_date_range_iteration(self, calendar: CostaRicaCalendar) -> None:
        """Test iteration over dates."""
        start = date(2024, 7, 29)
        end = date(2024, 7, 31)
        dr = DateRange(start, end, calendar)
        
        dates = list(dr)
        assert len(dates) == 3
        assert dates[0] == date(2024, 7, 29)
        assert dates[2] == date(2024, 7, 31)
    
    def test_date_range_calendar_days(self, calendar: CostaRicaCalendar) -> None:
        """Test calendar_days method."""
        start = date(2024, 7, 29)
        end = date(2024, 7, 31)
        dr = DateRange(start, end, calendar)
        
        dates = dr.calendar_days()
        assert len(dates) == 3
    
    def test_date_range_business_days(self, calendar: CostaRicaCalendar) -> None:
        """Test business_days method."""
        start = date(2024, 7, 29)  # Monday
        end = date(2024, 8, 6)     # Tuesday next week
        dr = DateRange(start, end, calendar)

        business_dates = dr.business_days()
        assert len(business_dates) == 7
    
    def test_date_range_invalid_end_raises_error(self, calendar: CostaRicaCalendar) -> None:
        """Test end before start raises error."""
        with pytest.raises(ValueError):
            DateRange(date(2024, 8, 2), date(2024, 7, 29), calendar)


class TestBusinessDayCalculator:
    """Tests for BusinessDayCalculator utility."""
    
    @pytest.fixture
    def calendar(self) -> CostaRicaCalendar:
        """Create test calendar."""
        return CostaRicaCalendar()
    
    def test_days_between(self, calendar: CostaRicaCalendar) -> None:
        """Test days_between calculation."""
        result = BusinessDayCalculator.days_between(
            date(2024, 7, 29),
            date(2024, 8, 2),
            calendar
        )
        assert result == 4  # 4 calendar days between
    
    def test_business_days_between(self, calendar: CostaRicaCalendar) -> None:
        """Test business_days_between calculation."""
        result = BusinessDayCalculator.business_days_between(
            date(2024, 7, 29),
            date(2024, 8, 6),
            calendar
        )
        assert result == 7
    
    def test_add_business_days(self, calendar: CostaRicaCalendar) -> None:
        """Test add_business_days utility."""
        result = BusinessDayCalculator.add_business_days(
            date(2024, 7, 29),
            4,
            calendar
        )
        # 4 business days from Monday: Tue, Wed, Thu, Fri
        assert result == date(2024, 8, 2)
    
    def test_next_business_day(self, calendar: CostaRicaCalendar) -> None:
        """Test next_business_day utility."""
        result = BusinessDayCalculator.next_business_day(
            date(2024, 7, 26),  # Friday
            calendar
        )
        assert result.weekday() == 0  # Monday
    
    def test_previous_business_day(self, calendar: CostaRicaCalendar) -> None:
        """Test previous_business_day utility."""
        result = BusinessDayCalculator.previous_business_day(
            date(2024, 7, 29),  # Monday
            calendar
        )
        assert result.weekday() == 4  # Friday
