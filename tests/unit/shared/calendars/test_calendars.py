"""Tests for calendars and date conventions modules.

Comprehensive tests for BusinessCalendar, DayCountConvention, and related types.
"""

import pytest
from datetime import date
from decimal import Decimal

from src.aip.shared.calendars import (
    CostaRicaCalendar,
    CostaRicaHolidayProvider,
    CostaRicaStatutoryHolidayProvider,
    InstitutionalHolidayProvider,
    WeekendRules,
)
from src.aip.shared.conventions import (
    DayCountConvention,
    Frequency,
    CouponConvention,
    BusinessDayConvention,
)


class TestCostaRicaHolidayProvider:
    """Tests for CostaRica holiday provider."""
    
    def test_new_years_day_is_holiday(self) -> None:
        """Test January 1 is holiday."""
        provider = CostaRicaHolidayProvider()
        assert provider.is_holiday(date(2024, 1, 1)) is True
    
    def test_christmas_day_is_holiday(self) -> None:
        """Test December 25 is holiday."""
        provider = CostaRicaHolidayProvider()
        assert provider.is_holiday(date(2024, 12, 25)) is True
    
    def test_regular_day_is_not_holiday(self) -> None:
        """Test regular day is not holiday."""
        provider = CostaRicaHolidayProvider()
        assert provider.is_holiday(date(2024, 6, 15)) is False
    
    def test_get_holidays_in_range(self) -> None:
        """Test getting holidays in date range."""
        provider = CostaRicaHolidayProvider()
        holidays = provider.get_holidays(date(2024, 1, 1), date(2024, 1, 31))
        assert len(holidays) > 0
        assert date(2024, 1, 1) in holidays
    
    def test_easter_holidays_calculated(self) -> None:
        """Test Easter-based holidays are calculated."""
        provider = CostaRicaHolidayProvider()
        # Easter 2024 is March 31
        # Holy Thursday is 3 days before = March 28
        assert provider.is_holiday(date(2024, 3, 28)) is True  # Holy Thursday

    def test_august_2_is_not_universal_national_holiday_by_default(self) -> None:
        """Test August 2 is not treated as universal banking holiday."""
        provider = CostaRicaHolidayProvider()
        assert provider.is_holiday(date(2024, 8, 2)) is False

    def test_august_2_can_be_enabled_as_institutional_holiday(self) -> None:
        """Test August 2 can be enabled for institutions."""
        provider = CostaRicaHolidayProvider(include_august_2_as_institutional=True)
        assert provider.is_holiday(date(2024, 8, 2)) is True

    def test_custom_institutional_holiday_by_year(self) -> None:
        """Test custom institutional holidays are configurable by year."""
        provider = CostaRicaHolidayProvider(
            institutional_holidays_by_year={
                2024: {date(2024, 11, 29)},
                2025: {date(2025, 11, 28)},
            }
        )

        assert provider.is_holiday(date(2024, 11, 29)) is True
        assert provider.is_holiday(date(2025, 11, 28)) is True
        assert provider.is_holiday(date(2026, 11, 27)) is False


class TestCostaRicaHolidayProviderSeparation:
    """Regression tests for statutory vs institutional separation."""

    def test_institutional_holiday_does_not_modify_statutory_provider(self) -> None:
        """Custom institutional holiday must not alter statutory national calendar."""
        statutory = CostaRicaStatutoryHolidayProvider()
        institutional = CostaRicaHolidayProvider(
            institutional_holidays_by_year={2024: {date(2024, 11, 29)}}
        )

        assert statutory.is_holiday(date(2024, 11, 29)) is False
        assert institutional.is_holiday(date(2024, 11, 29)) is True
        assert statutory.is_holiday(date(2024, 1, 1)) is True
        assert institutional.is_holiday(date(2024, 1, 1)) is True

    def test_institutional_provider_directly_configurable_by_year(self) -> None:
        """InstitutionalHolidayProvider supports explicit per-year configuration."""
        provider = InstitutionalHolidayProvider(
            holidays_by_year={2024: {date(2024, 6, 17)}},
            include_august_2=False,
        )

        assert provider.is_holiday(date(2024, 6, 17)) is True
        assert provider.is_holiday(date(2025, 6, 17)) is False

    def test_institutional_provider_can_include_august_2(self) -> None:
        """Institutional provider can include August 2 without changing statutory set."""
        provider = InstitutionalHolidayProvider(include_august_2=True)
        assert provider.is_holiday(date(2024, 8, 2)) is True


class TestCostaRicaCalendar:
    """Tests for Costa Rica business calendar."""
    
    def test_monday_is_business_day(self) -> None:
        """Test Monday is business day."""
        calendar = CostaRicaCalendar()
        # 2024-07-29 is a Monday
        assert calendar.is_business_day(date(2024, 7, 29)) is True
    
    def test_saturday_is_not_business_day(self) -> None:
        """Test Saturday is not business day."""
        calendar = CostaRicaCalendar()
        # 2024-07-27 is a Saturday
        assert calendar.is_business_day(date(2024, 7, 27)) is False
    
    def test_sunday_is_not_business_day(self) -> None:
        """Test Sunday is not business day."""
        calendar = CostaRicaCalendar()
        # 2024-07-28 is a Sunday
        assert calendar.is_business_day(date(2024, 7, 28)) is False
    
    def test_holiday_is_not_business_day(self) -> None:
        """Test holiday is not business day."""
        calendar = CostaRicaCalendar()
        # 2024-01-01 is New Year (Monday but holiday)
        assert calendar.is_business_day(date(2024, 1, 1)) is False
    
    def test_next_business_day_from_friday(self) -> None:
        """Test next business day from Friday goes to Monday."""
        calendar = CostaRicaCalendar()
        # 2024-07-26 is Friday
        result = calendar.next_business_day(date(2024, 7, 26))
        # Should skip Saturday and Sunday, return Monday 2024-07-29
        assert result.weekday() == 0  # Monday
    
    def test_previous_business_day_from_monday(self) -> None:
        """Test previous business day from Monday goes to Friday."""
        calendar = CostaRicaCalendar()
        # 2024-07-29 is Monday
        result = calendar.previous_business_day(date(2024, 7, 29))
        # Should skip Sunday and Saturday, return Friday 2024-07-26
        assert result.weekday() == 4  # Friday
    
    def test_business_days_between(self) -> None:
        """Test counting business days between dates."""
        calendar = CostaRicaCalendar()
        # One week and one day: Mon 7/29 to Tue 8/6
        start = date(2024, 7, 29)
        end = date(2024, 8, 6)
        count = calendar.business_days_between(start, end)
        assert count == 7  # Mon, Tue, Wed, Thu, Fri, Mon, Tue


class TestDayCountConvention:
    """Tests for day count conventions."""
    
    def test_actual_365_convention(self) -> None:
        """Test ACTUAL/365 day count."""
        convention = DayCountConvention.ACTUAL_365
        start = date(2024, 1, 1)
        end = date(2024, 1, 11)
        # 10 days / 365 = 0.0274
        result = convention.calculate_year_fraction(start, end)
        expected = Decimal(10) / Decimal(365)
        assert abs(result - expected) < Decimal("0.001")
    
    def test_actual_360_convention(self) -> None:
        """Test ACTUAL/360 day count."""
        convention = DayCountConvention.ACTUAL_360
        start = date(2024, 1, 1)
        end = date(2024, 1, 11)
        result = convention.calculate_year_fraction(start, end)
        expected = Decimal(10) / Decimal(360)
        assert abs(result - expected) < Decimal("0.001")
    
    def test_thirty_360_convention(self) -> None:
        """Test 30/360 day count."""
        convention = DayCountConvention.THIRTY_360
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        result = convention.calculate_year_fraction(start, end)
        # 30 days / 360 = 0.0833
        assert result > 0


class TestFrequency:
    """Tests for Frequency enumeration."""
    
    def test_annual_frequency(self) -> None:
        """Test annual frequency."""
        freq = Frequency.ANNUAL
        assert freq.months_between_payments() == 12
        assert freq.days_between_payments() == 360
    
    def test_semi_annual_frequency(self) -> None:
        """Test semi-annual frequency."""
        freq = Frequency.SEMI_ANNUAL
        assert freq.months_between_payments() == 6
        assert freq.days_between_payments() == 180
    
    def test_quarterly_frequency(self) -> None:
        """Test quarterly frequency."""
        freq = Frequency.QUARTERLY
        assert freq.months_between_payments() == 3
        assert freq.days_between_payments() == 90
    
    def test_monthly_frequency(self) -> None:
        """Test monthly frequency."""
        freq = Frequency.MONTHLY
        assert freq.months_between_payments() == 1
        assert freq.days_between_payments() == 30


class TestCouponConvention:
    """Tests for CouponConvention."""
    
    def test_coupon_convention_creation(self) -> None:
        """Test CouponConvention can be created."""
        coupon = CouponConvention(
            frequency=Frequency.SEMI_ANNUAL,
            day_count=DayCountConvention.ACTUAL_360,
            basis_month=3,
            basis_day=15,
        )
        assert coupon.frequency == Frequency.SEMI_ANNUAL
    
    def test_next_coupon_date(self) -> None:
        """Test next coupon date calculation."""
        coupon = CouponConvention(
            frequency=Frequency.SEMI_ANNUAL,
            day_count=DayCountConvention.ACTUAL_360,
            basis_month=3,
            basis_day=15,
        )
        # From January, next coupon should be March 15
        result = coupon.next_coupon_date(date(2024, 1, 15))
        assert result.month == 3
        assert result.day == 15
    
    def test_previous_coupon_date(self) -> None:
        """Test previous coupon date calculation."""
        coupon = CouponConvention(
            frequency=Frequency.SEMI_ANNUAL,
            day_count=DayCountConvention.ACTUAL_360,
            basis_month=3,
            basis_day=15,
        )
        # From May, previous coupon should be March 15
        result = coupon.previous_coupon_date(date(2024, 5, 15))
        assert result.month == 3
        assert result.day == 15
    
    def test_coupon_convention_invalid_month_raises_error(self) -> None:
        """Test invalid month raises error."""
        with pytest.raises(ValueError):
            CouponConvention(
                frequency=Frequency.SEMI_ANNUAL,
                day_count=DayCountConvention.ACTUAL_360,
                basis_month=13,  # Invalid
                basis_day=15,
            )
    
    def test_coupon_convention_invalid_day_raises_error(self) -> None:
        """Test invalid day raises error."""
        with pytest.raises(ValueError):
            CouponConvention(
                frequency=Frequency.SEMI_ANNUAL,
                day_count=DayCountConvention.ACTUAL_360,
                basis_month=3,
                basis_day=32,  # Invalid
            )


class TestBusinessDayConvention:
    """Tests for BusinessDayConvention."""
    
    def test_following_convention_advances_date(self) -> None:
        """Test FOLLOWING advances to next business day."""
        # 2024-07-27 is Saturday
        saturday = date(2024, 7, 27)
        is_business_day = lambda d: d.weekday() < 5  # Mon-Fri
        
        result = BusinessDayConvention.FOLLOWING.adjust(saturday, is_business_day)
        assert result.weekday() == 0  # Monday
    
    def test_preceding_convention_goes_back(self) -> None:
        """Test PRECEDING goes to previous business day."""
        # 2024-07-28 is Sunday
        sunday = date(2024, 7, 28)
        is_business_day = lambda d: d.weekday() < 5  # Mon-Fri
        
        result = BusinessDayConvention.PRECEDING.adjust(sunday, is_business_day)
        assert result.weekday() == 4  # Friday
    
    def test_unadjusted_convention_no_change(self) -> None:
        """Test UNADJUSTED doesn't change date."""
        saturday = date(2024, 7, 27)
        is_business_day = lambda d: d.weekday() < 5
        
        result = BusinessDayConvention.UNADJUSTED.adjust(saturday, is_business_day)
        assert result == saturday

    def test_actual_actual_convention_same_year(self) -> None:
        """Test ACTUAL/ACTUAL for same year."""
        convention = DayCountConvention.ACTUAL_ACTUAL
        # Non-leap year
        result = convention.calculate_year_fraction(date(2023, 1, 1), date(2023, 12, 31))
        assert result == Decimal(364) / Decimal(365)
    
    def test_actual_actual_convention_leap_year(self) -> None:
        """Test ACTUAL/ACTUAL for leap year."""
        convention = DayCountConvention.ACTUAL_ACTUAL
        # 2024 is leap year
        result = convention.calculate_year_fraction(date(2024, 1, 1), date(2024, 12, 31))
        expected = Decimal(365) / Decimal(366)
        assert abs(result - expected) < Decimal("0.0000000001")
    
    def test_thirty_360_convention(self) -> None:
        """Test 30/360 day count."""
        convention = DayCountConvention.THIRTY_360
        start = date(2024, 1, 31)
        end = date(2024, 3, 31)
        result = convention.calculate_year_fraction(start, end)
        # 30/360: (30-30) + 30 + 30 = 60 days / 360
        assert result > 0
    
    def test_thirty_e_360_convention(self) -> None:
        """Test 30E/360 day count."""
        convention = DayCountConvention.THIRTY_E_360
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)
        result = convention.calculate_year_fraction(start, end)
        assert result > 0
    
    def test_frequency_string_representation(self) -> None:
        """Test frequency enum string representation."""
        assert str(Frequency.ANNUAL) == "Frequency.ANNUAL"
        assert str(Frequency.SEMI_ANNUAL) == "Frequency.SEMI_ANNUAL"
        assert str(Frequency.QUARTERLY) == "Frequency.QUARTERLY"
        assert str(Frequency.MONTHLY) == "Frequency.MONTHLY"

    def test_actual_actual_convention_multi_year(self) -> None:
        """Test ACTUAL/ACTUAL for multi-year period."""
        convention = DayCountConvention.ACTUAL_ACTUAL
        start = date(2023, 6, 1)
        end = date(2025, 6, 1)

        result = convention.calculate_year_fraction(start, end)

        assert result > Decimal("1.99")
        assert result < Decimal("2.01")

    def test_is_leap_year_helper(self) -> None:
        """Test leap-year helper method."""
        assert DayCountConvention._is_leap_year(2024) is True
        assert DayCountConvention._is_leap_year(2023) is False
        assert DayCountConvention._is_leap_year(1900) is False
        assert DayCountConvention._is_leap_year(2000) is True

    def test_modified_following_convention_cross_month(self) -> None:
        """Test MODIFIED_FOLLOWING moves back if next business day is next month."""
        convention = BusinessDayConvention.MODIFIED_FOLLOWING

        def is_business_day(d: date) -> bool:
            return d.weekday() < 5

        # 2025-05-31 is Saturday. Following is 2025-06-02 (next month),
        # so modified following should move back to 2025-05-30.
        result = convention.adjust(date(2025, 5, 31), is_business_day)
        assert result == date(2025, 5, 30)

    def test_modified_preceding_convention_cross_month(self) -> None:
        """Test MODIFIED_PRECEDING moves forward if previous business day is prior month."""
        convention = BusinessDayConvention.MODIFIED_PRECEDING

        def is_business_day(d: date) -> bool:
            # Previous business day backward is May 31, fallback target is June 3.
            return d in {date(2024, 5, 31), date(2024, 6, 3)}

        # Sunday at month start. Preceding business day would be in May,
        # so modified preceding should move forward into June.
        result = convention.adjust(date(2024, 6, 2), is_business_day)
        assert result == date(2024, 6, 3)

    def test_adjust_returns_target_when_already_business_day(self) -> None:
        """Test adjust returns same date when target is already business day."""
        target = date(2024, 7, 29)
        is_business_day = lambda d: d.weekday() < 5
        assert BusinessDayConvention.FOLLOWING.adjust(target, is_business_day) == target
    
    def test_coupon_next_coupon_different_frequencies(self) -> None:
        """Test next coupon for different frequencies."""
        # Semi-annual
        coupon_semi = CouponConvention(
            frequency=Frequency.SEMI_ANNUAL,
            day_count=DayCountConvention.ACTUAL_360,
            basis_month=3,
            basis_day=15,
        )
        # From June, next should be September
        result = coupon_semi.next_coupon_date(date(2024, 6, 15))
        assert result.month == 9
    
    def test_coupon_quarterly(self) -> None:
        """Test quarterly coupon dates."""
        coupon_q = CouponConvention(
            frequency=Frequency.QUARTERLY,
            day_count=DayCountConvention.ACTUAL_360,
            basis_month=1,
            basis_day=15,
        )
        result = coupon_q.next_coupon_date(date(2024, 2, 15))
        assert result.month == 4

