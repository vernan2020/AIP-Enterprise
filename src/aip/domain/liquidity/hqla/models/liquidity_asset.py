from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from aip.domain.liquidity.hqla.exceptions import HQLAError


@dataclass(frozen=True, slots=True)
class LiquidityAsset:
    """Generic liquid asset representation used for HQLA evaluation."""

    identifier: str
    instrument: str
    issuer: str
    currency: str
    market_value: Decimal
    haircut: Decimal
    encumbered: bool
    marketability_indicators: dict[str, object] = field(default_factory=dict)
    settlement_indicators: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.identifier or not self.identifier.strip():
            raise HQLAError("Identifier is required")
        if not self.instrument or not self.instrument.strip():
            raise HQLAError("Instrument is required")
        if not self.issuer or not self.issuer.strip():
            raise HQLAError("Issuer is required")
        if not self.currency or not self.currency.strip():
            raise HQLAError("Currency is required")
        if not isinstance(self.market_value, Decimal):
            raise HQLAError("Market value must be a Decimal")
        if self.market_value.is_nan() or self.market_value.is_infinite():
            raise HQLAError("Market value must be finite")
        if self.market_value < 0:
            raise HQLAError("Market value cannot be negative")
        if not isinstance(self.haircut, Decimal):
            raise HQLAError("Haircut must be a Decimal")
        if self.haircut.is_nan() or self.haircut.is_infinite():
            raise HQLAError("Haircut must be finite")
        if self.haircut < 0:
            raise HQLAError("Haircut cannot be negative")
        if self.haircut > Decimal("1"):
            raise HQLAError("Haircut cannot exceed one")
        if not isinstance(self.marketability_indicators, dict):
            raise HQLAError("Marketability indicators must be a dictionary")
        if not isinstance(self.settlement_indicators, dict):
            raise HQLAError("Settlement indicators must be a dictionary")
        if not isinstance(self.metadata, dict):
            raise HQLAError("Metadata must be a dictionary")
        if self.metadata is not None:
            object.__setattr__(self, "metadata", dict(self.metadata))
            object.__setattr__(
                self, "marketability_indicators", dict(self.marketability_indicators)
            )
            object.__setattr__(self, "settlement_indicators", dict(self.settlement_indicators))

    @property
    def adjusted_value(self) -> Decimal:
        return self.market_value * (Decimal("1") - self.haircut)
