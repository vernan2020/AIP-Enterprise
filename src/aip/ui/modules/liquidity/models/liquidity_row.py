from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LiquidityRow:
    """Normalized presentation row for liquidity detail tables."""

    section: str
    label: str
    value: str
    bucket: str = ""
    status: str = ""
    policy_reference: str = ""
    calculation_id: str | None = None
    correlation_id: str | None = None
    issuer: str = ""
    currency: str = ""
    classification: str = ""
    market_value_crc: float = 0.0
    factor: float = 0.0
    maturity_date: str = ""
    days_to_maturity: int | None = None
