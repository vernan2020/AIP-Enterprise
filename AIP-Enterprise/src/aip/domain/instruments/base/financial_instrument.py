from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.instruments.exceptions import InstrumentValidationError
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule
from aip.shared.conventions import DayCountConvention


@dataclass(slots=True)
class FinancialInstrument(ABC):
    """Abstract base class for all financial instruments."""

    isin: str
    name: str
    issuer: Issuer
    currency: str
    settlement_calendar: str
    business_day_convention: str
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
        self.nominal_value = self._ensure_decimal(self.nominal_value)
        self.book_value = self._ensure_decimal(self.book_value)
        self.market_value = self._ensure_decimal(self.market_value)
        self.face_value = self._ensure_decimal(self.face_value)
        self.outstanding_amount = self._ensure_decimal(self.outstanding_amount)
        self.yield_rate = self._ensure_decimal(self.yield_rate)
        self.duration = self._ensure_decimal(self.duration)
        self.modified_duration = self._ensure_decimal(self.modified_duration)
        self.convexity = self._ensure_decimal(self.convexity)
        self.dirty_price = self._ensure_decimal(self.dirty_price)
        self.clean_price = self._ensure_decimal(self.clean_price)
        self.accrued_interest = self._ensure_decimal(self.accrued_interest)
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
