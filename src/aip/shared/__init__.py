"""Shared Foundation module for AIP Enterprise.

This module provides foundational utilities, value objects, and abstractions
used across the AIP Enterprise application.

Sub-packages:
    validation: Input validation and guard clauses.
    math: Safe mathematical operations for financial calculations.
    conventions: Financial conventions (day counts, frequencies, etc.).
    calendars: Business calendar implementations.
    dates: Business date value objects and utilities.
    money: Money and currency value objects.
    serialization: JSON serialization support.
    collections: Immutable collection types.
"""

# Validation exports
from aip.shared.validation import (
    Guard,
    Validators,
    ValidationException,
    RequiredValueError,
    PositiveValueError,
    NotEmptyError,
    RangeError,
    InvalidFormatError,
)

# Math exports
from aip.shared.math import (
    SafeDecimal,
    Percentage,
    WeightedAverage,
    LinearInterpolation,
)

# Conventions exports
from aip.shared.conventions import (
    DayCountConvention,
    Frequency,
    CouponConvention,
    BusinessDayConvention,
)

# Calendars exports
from aip.shared.calendars import (
    BusinessCalendar,
    HolidayProvider,
    WeekendRules,
    CostaRicaCalendar,
    CostaRicaHolidayProvider,
)

# Dates exports
from aip.shared.dates import (
    BusinessDate,
    BusinessPeriod,
    DateRange,
    BusinessDayCalculator,
)

# Money exports
from aip.shared.money import (
    Currency,
    Money,
    ExchangeRate,
    MoneyArithmetic,
)

# Serialization exports
from aip.shared.serialization import (
    JsonSerializer,
    DecimalEncoder,
    DateEncoder,
)

# Collections exports
from aip.shared.collections import (
    ImmutableList,
    ImmutableDict,
    ImmutableSet,
)

__all__ = [
    # Validation
    "Guard",
    "Validators",
    "ValidationException",
    "RequiredValueError",
    "PositiveValueError",
    "NotEmptyError",
    "RangeError",
    "InvalidFormatError",
    # Math
    "SafeDecimal",
    "Percentage",
    "WeightedAverage",
    "LinearInterpolation",
    # Conventions
    "DayCountConvention",
    "Frequency",
    "CouponConvention",
    "BusinessDayConvention",
    # Calendars
    "BusinessCalendar",
    "HolidayProvider",
    "WeekendRules",
    "CostaRicaCalendar",
    "CostaRicaHolidayProvider",
    # Dates
    "BusinessDate",
    "BusinessPeriod",
    "DateRange",
    "BusinessDayCalculator",
    # Money
    "Currency",
    "Money",
    "ExchangeRate",
    "MoneyArithmetic",
    # Serialization
    "JsonSerializer",
    "DecimalEncoder",
    "DateEncoder",
    # Collections
    "ImmutableList",
    "ImmutableDict",
    "ImmutableSet",
]
