from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class DurationResult:
    modified_duration: Decimal | None
    method: str
    source: str
    next_repricing_date: date | None = None
    diagnostic: str | None = None


class PortfolioDurationService:
    """Institutional duration rules for configured portfolio positions."""

    _PERIOD_MONTHS = {
        "mensual": 1,
        "monthly": 1,
        "trimestral": 3,
        "quarterly": 3,
        "semestral": 6,
        "semiannual": 6,
        "anual": 12,
        "annual": 12,
    }
    _MATURITY_PROXY_PRODUCTS = {"cdp-ci", "icp", "mil"}

    @classmethod
    def calculate(cls, position: dict[str, Any], valuation_date: date) -> DurationResult:
        if cls._is_variable(position):
            return cls._variable_rate_duration(position, valuation_date)

        product = cls._text(position.get("product_code"))
        periodicity = cls._text(position.get("periodicity"))

        if product in cls._MATURITY_PROXY_PRODUCTS and periodicity in {
            "",
            "no aplica",
            "noaplica",
        }:
            return cls._maturity_proxy(position, valuation_date)

        if periodicity in cls._PERIOD_MONTHS:
            return cls._fixed_rate_duration(position, valuation_date)

        return DurationResult(
            None,
            "NOT_APPLICABLE",
            "INSTITUTIONAL_CLASSIFICATION",
            diagnostic="No supported duration treatment for position",
        )

    @classmethod
    def _variable_rate_duration(
        cls, position: dict[str, Any], valuation_date: date
    ) -> DurationResult:
        months = cls._PERIOD_MONTHS.get(cls._text(position.get("periodicity")))
        last_payment = cls._as_date(position.get("last_interest_payment_date"))
        maturity = cls._as_date(position.get("maturity_date"))

        if months is None:
            return DurationResult(
                None,
                "REPRICING_UNAVAILABLE",
                "MASTER_VARIABLE_RATE",
                diagnostic="Variable-rate position has unsupported periodicity",
            )

        anchor = last_payment or valuation_date
        next_repricing = cls._advance_months(anchor, months)
        while next_repricing <= valuation_date:
            next_repricing = cls._advance_months(next_repricing, months)

        if maturity is not None and next_repricing > maturity:
            next_repricing = maturity

        days = max((next_repricing - valuation_date).days, 0)
        return DurationResult(
            Decimal(days) / Decimal("365"),
            "NEXT_REPRICING",
            "MASTER_VARIABLE_RATE",
            next_repricing_date=next_repricing,
        )

    @classmethod
    def _maturity_proxy(
        cls, position: dict[str, Any], valuation_date: date
    ) -> DurationResult:
        maturity = cls._as_date(position.get("maturity_date"))
        if maturity is None:
            return DurationResult(
                None,
                "MATURITY_UNAVAILABLE",
                "CONTRACTUAL_MATURITY",
                diagnostic="Maturity date is unavailable",
            )
        days = max((maturity - valuation_date).days, 0)
        return DurationResult(
            Decimal(days) / Decimal("365"),
            "MATURITY_PROXY",
            "CONTRACTUAL_MATURITY",
        )

    @classmethod
    def _fixed_rate_duration(
        cls, position: dict[str, Any], valuation_date: date
    ) -> DurationResult:
        market_yield = cls._decimal(position.get("market_yield"))
        coupon_rate = cls._decimal(position.get("nominal_rate"))
        nominal = cls._decimal(position.get("nominal"))
        maturity = cls._as_date(position.get("maturity_date"))
        months = cls._PERIOD_MONTHS.get(cls._text(position.get("periodicity")))

        if market_yield is None or market_yield <= 0:
            return DurationResult(
                None,
                "MARKET_DURATION_UNAVAILABLE",
                "PIPCA_MARKET_YIELD",
                diagnostic="PiPCA market yield is unavailable",
            )
        if coupon_rate is None or nominal is None or nominal <= 0 or maturity is None or months is None:
            return DurationResult(
                None,
                "MARKET_DURATION_UNAVAILABLE",
                "PIPCA_MARKET_YIELD",
                diagnostic="Insufficient fixed-rate cash-flow data",
            )
        if maturity <= valuation_date:
            return DurationResult(Decimal("0"), "MATURED", "CONTRACTUAL_MATURITY")

        y = cls._rate_decimal(market_yield)
        c = cls._rate_decimal(coupon_rate)
        frequency = Decimal(12) / Decimal(months)
        coupon = nominal * c / frequency

        payment_dates: list[date] = []
        current = maturity
        while current > valuation_date:
            payment_dates.append(current)
            current = cls._advance_months(current, -months)
        payment_dates.sort()

        pv_total = Decimal("0")
        weighted_time = Decimal("0")
        for payment_date in payment_dates:
            years = Decimal((payment_date - valuation_date).days) / Decimal("365")
            amount = coupon + (nominal if payment_date == maturity else Decimal("0"))
            pv = amount / ((Decimal("1") + y) ** years)
            pv_total += pv
            weighted_time += years * pv

        if pv_total <= 0:
            return DurationResult(
                None,
                "MARKET_DURATION_UNAVAILABLE",
                "PIPCA_MARKET_YIELD",
                diagnostic="Present value is non-positive",
            )

        macaulay = weighted_time / pv_total
        modified = macaulay / (Decimal("1") + (y / frequency))
        return DurationResult(modified, "MODIFIED_DURATION", "PIPCA_MARKET_YIELD")

    @staticmethod
    def _is_variable(position: dict[str, Any]) -> bool:
        return PortfolioDurationService._text(position.get("variable_rate_flag")) in {
            "s",
            "si",
            "sí",
            "yes",
            "y",
            "true",
            "1",
        }

    @staticmethod
    def _rate_decimal(value: Decimal) -> Decimal:
        return value / Decimal("100") if abs(value) > Decimal("1") else value

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, ValueError, TypeError):
            return None

    @staticmethod
    def _as_date(value: Any) -> date | None:
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value:
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip().casefold()

    @staticmethod
    def _advance_months(value: date, months: int) -> date:
        month_index = value.year * 12 + value.month - 1 + months
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
