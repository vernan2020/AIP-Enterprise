from __future__ import annotations

import math
from decimal import Decimal

from aip.domain.financial_math.exceptions import InvalidRateError


def _validate_rate(rate: Decimal) -> None:
    if rate.is_nan() or rate.is_infinite():
        raise InvalidRateError("Rate must be finite")


def _validate_frequency(frequency: int) -> None:
    if frequency <= 0:
        raise InvalidRateError("Compounding frequency must be positive")


def _power(base: Decimal, exponent: Decimal) -> Decimal:
    return Decimal(str(pow(float(base), float(exponent))))


def accumulation_factor(
    rate: Decimal,
    time: Decimal,
    *,
    compounding: str = "annual",
    frequency: int = 1,
) -> Decimal:
    """Calculate a growth factor over a time horizon."""
    _validate_rate(rate)
    _validate_frequency(frequency)
    compounding_key = compounding.lower()
    if compounding_key == "simple":
        return Decimal("1") + rate * time
    if compounding_key == "continuous":
        return Decimal(str(math.exp(float(rate * time))))
    if compounding_key == "annual":
        periods = Decimal(frequency) * time
        return _power(Decimal("1") + rate / Decimal(frequency), periods)
    if compounding_key == "semiannual":
        return _power(Decimal("1") + rate / Decimal("2"), Decimal("2") * time)
    if compounding_key == "quarterly":
        return _power(Decimal("1") + rate / Decimal("4"), Decimal("4") * time)
    if compounding_key == "monthly":
        return _power(Decimal("1") + rate / Decimal("12"), Decimal("12") * time)
    raise InvalidRateError("Unsupported compounding convention")


def discount_factor(
    rate: Decimal,
    time: Decimal,
    *,
    compounding: str = "annual",
    frequency: int = 1,
) -> Decimal:
    """Discount one unit of currency back to present value."""
    factor = accumulation_factor(rate, time, compounding=compounding, frequency=frequency)
    if factor <= 0:
        raise InvalidRateError("Discount factor is undefined")
    return Decimal("1") / factor


def equivalent_rate(
    rate: Decimal,
    *,
    from_compounding: str,
    to_compounding: str,
    frequency: int = 1,
) -> Decimal:
    """Convert a rate to an equivalent rate under another compounding convention."""
    _validate_rate(rate)
    _validate_frequency(frequency)
    from_key = from_compounding.lower()
    to_key = to_compounding.lower()
    if from_key == to_key:
        return rate
    if from_key == "continuous":
        effective_annual = Decimal(str(math.exp(float(rate)) - 1.0))
    elif from_key == "simple":
        effective_annual = rate
    else:
        effective_annual = _power(Decimal("1") + rate / Decimal(frequency), Decimal(frequency)) - Decimal("1")
    if to_key == "continuous":
        return Decimal(str(math.log(float(effective_annual + Decimal("1")))))
    if to_key == "simple":
        return effective_annual
    target_frequency = {"annual": 1, "semiannual": 2, "quarterly": 4, "monthly": 12}[to_key]
    return Decimal(target_frequency) * (_power(Decimal("1") + effective_annual, Decimal("1") / Decimal(target_frequency)) - Decimal("1"))
