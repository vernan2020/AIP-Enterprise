from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from aip.core.exceptions import ValidationError
from aip.domain.instruments.exceptions import InstrumentValidationError
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule
from aip.shared.conventions import BusinessDayConvention, DayCountConvention


@dataclass(slots=True)
class FinancialInstrument(ABC):
    """Abstract base class for all financial instruments."""

    isin: str
    name: str
    issuer: Issuer
    currency: str
    settlement_calendar: str
    business_day_convention: str | BusinessDayConvention
    day_count_convention: DayCountConvention
    issue_date: date
    settlement_date: date
    maturity_date: date
    coupon_schedule: CouponSchedule | None
    nominal_value: Decimal
    book_value: Decimal
    market_value: Decimal
    face_value: Decimal
    outstanding_amount: Decimal
    yield_rate: Decimal
    duration: Decimal
    modified_duration: Decimal
    convexity: Decimal
    dirty_price: Decimal
    clean_price: Decimal
    accrued_interest: Decimal
    settlement_currency: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate_common_rules()
        self._initialize_defaults()

    def _validate_common_rules(self) -> None:
        if not self.isin or len(self.isin.strip()) < 3:
            raise InstrumentValidationError("ISIN must be provided")
        if not self.name.strip():
            raise InstrumentValidationError("Instrument name must be provided")
        if self.issue_date > self.maturity_date:
            raise InstrumentValidationError("Issue date cannot be after maturity date")
        if self.settlement_date > self.maturity_date:
            raise InstrumentValidationError("Settlement date cannot be after maturity date")
        if self.nominal_value <= 0:
            raise InstrumentValidationError("Nominal value must be positive")
        if self.face_value <= 0:
            raise InstrumentValidationError("Face value must be positive")
        if self.outstanding_amount <= 0:
            raise InstrumentValidationError("Outstanding amount must be positive")
        if self.yield_rate < 0:
            raise InstrumentValidationError("Yield rate cannot be negative")

    def _initialize_defaults(self) -> None:
        self._ensure_decimal(self.nominal_value)
        self._ensure_decimal(self.book_value)
        self._ensure_decimal(self.market_value)
        self._ensure_decimal(self.face_value)
        self._ensure_decimal(self.outstanding_amount)
        self._ensure_decimal(self.yield_rate)
        self._ensure_decimal(self.duration)
        self._ensure_decimal(self.modified_duration)
        self._ensure_decimal(self.convexity)
        self._ensure_decimal(self.dirty_price)
        self._ensure_decimal(self.clean_price)
        self._ensure_decimal(self.accrued_interest)
        self.coupon_schedule = self.coupon_schedule or CouponSchedule()

    @staticmethod
    def _ensure_decimal(value: Decimal | int | float) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            return Decimal(value)
        return Decimal(str(value))

    @property
    def instrument_name(self) -> str:
        return self.name

    @property
    def settlement_currency_code(self) -> str:
        return self.settlement_currency or self.currency

    @property
    def clean_price(self) -> Decimal:
        return self._clean_price

    @clean_price.setter
    def clean_price(self, value: Decimal) -> None:
        self._clean_price = self._ensure_decimal(value)

    @property
    def dirty_price(self) -> Decimal:
        return self._dirty_price

    @dirty_price.setter
    def dirty_price(self, value: Decimal) -> None:
        self._dirty_price = self._ensure_decimal(value)

    @property
    def accrued_interest(self) -> Decimal:
        return self._accrued_interest

    @accrued_interest.setter
    def accrued_interest(self, value: Decimal) -> None:
        self._accrued_interest = self._ensure_decimal(value)

    @property
    def yield_rate(self) -> Decimal:
        return self._yield_rate

    @yield_rate.setter
    def yield_rate(self, value: Decimal) -> None:
        self._yield_rate = self._ensure_decimal(value)

    @property
    def duration(self) -> Decimal:
        return self._duration

    @duration.setter
    def duration(self, value: Decimal) -> None:
        self._duration = self._ensure_decimal(value)

    @property
    def modified_duration(self) -> Decimal:
        return self._modified_duration

    @modified_duration.setter
    def modified_duration(self, value: Decimal) -> None:
        self._modified_duration = self._ensure_decimal(value)

    @property
    def convexity(self) -> Decimal:
        return self._convexity

    @convexity.setter
    def convexity(self, value: Decimal) -> None:
        self._convexity = self._ensure_decimal(value)

    @property
    def nominal_value(self) -> Decimal:
        return self._nominal_value

    @nominal_value.setter
    def nominal_value(self, value: Decimal) -> None:
        self._nominal_value = self._ensure_decimal(value)

    @property
    def book_value(self) -> Decimal:
        return self._book_value

    @book_value.setter
    def book_value(self, value: Decimal) -> None:
        self._book_value = self._ensure_decimal(value)

    @property
    def market_value(self) -> Decimal:
        return self._market_value

    @market_value.setter
    def market_value(self, value: Decimal) -> None:
        self._market_value = self._ensure_decimal(value)

    @property
    def face_value(self) -> Decimal:
        return self._face_value

    @face_value.setter
    def face_value(self, value: Decimal) -> None:
        self._face_value = self._ensure_decimal(value)

    @property
    def outstanding_amount(self) -> Decimal:
        return self._outstanding_amount

    @outstanding_amount.setter
    def outstanding_amount(self, value: Decimal) -> None:
        self._outstanding_amount = self._ensure_decimal(value)

    @property
    def isis(self) -> str:
        return self.isin

    @property
    def issuer_name(self) -> str:
        return self.issuer.name

    def to_dict(self) -> dict[str, Any]:
        return {
            "isin": self.isin,
            "name": self.name,
            "issuer": self.issuer.name,
            "currency": self.currency,
            "settlement_currency": self.settlement_currency_code,
            "issue_date": self.issue_date.isoformat(),
            "settlement_date": self.settlement_date.isoformat(),
            "maturity_date": self.maturity_date.isoformat(),
            "nominal_value": str(self.nominal_value),
            "book_value": str(self.book_value),
            "market_value": str(self.market_value),
            "face_value": str(self.face_value),
            "outstanding_amount": str(self.outstanding_amount),
            "yield_rate": str(self.yield_rate),
            "duration": str(self.duration),
            "modified_duration": str(self.modified_duration),
            "convexity": str(self.convexity),
            "dirty_price": str(self.dirty_price),
            "clean_price": str(self.clean_price),
            "accrued_interest": str(self.accrued_interest),
        }

    @abstractmethod
    def calculate_price(self) -> Decimal:
        """Calculate a price for the instrument."""

    @abstractmethod
    def calculate_yield(self) -> Decimal:
        """Calculate yield from price and cash flows."""
