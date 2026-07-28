from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from src.extensions.coopealianza.liquidity.mil.exceptions import MilValuationError


@dataclass(frozen=True, slots=True)
class MilAsset:
    """Immutable MIL collateral asset value object."""

    position_id: str
    instrument_id: str
    isin: str
    issuer: str
    issuer_category: str
    currency: str
    nominal_amount: Decimal
    market_value: Decimal
    accounting_value: Decimal
    classification: str
    encumbrance_status: str
    reserve_liquidity_status: str
    operational_availability: bool
    settlement_capability: str
    valuation_date: date
    market_price_date: date
    maturity_date: date
    portfolio_reference: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate()
        object.__setattr__(self, "metadata", dict(self.metadata))

    def _validate(self) -> None:
        for name in ("position_id", "instrument_id", "isin", "issuer", "currency", "classification", "portfolio_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise MilValuationError(f"{name} must be provided")
        for name in ("nominal_amount", "market_value", "accounting_value"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise MilValuationError(f"{name} must be a Decimal")
            try:
                if not value.is_finite():
                    raise MilValuationError(f"{name} must be finite")
            except InvalidOperation as exc:
                raise MilValuationError(f"{name} must be finite") from exc
            if name == "nominal_amount" and value < 0:
                raise MilValuationError("nominal_amount cannot be negative")
            if name in {"market_value", "accounting_value"} and value < 0:
                raise MilValuationError(f"{name} cannot be negative")
        for name in ("valuation_date", "market_price_date", "maturity_date"):
            value = getattr(self, name)
            if isinstance(value, date):
                continue
            if isinstance(value, str):
                try:
                    parsed = date.fromisoformat(value)
                except ValueError as exc:
                    raise MilValuationError(f"{name} must be a valid date") from exc
                object.__setattr__(self, name, parsed)
            else:
                raise MilValuationError(f"{name} must be a date")

        if self.valuation_date > self.market_price_date:
            raise MilValuationError("valuation_date cannot be after market_price_date")
        if self.market_price_date > self.maturity_date:
            raise MilValuationError("market_price_date cannot be after maturity_date")
        if self.valuation_date > self.maturity_date:
            raise MilValuationError("valuation_date cannot be after maturity_date")
