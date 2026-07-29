from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarketRow:
    issuer: str
    instrument: str
    currency: str
    recommendation: str
    confidence: str
    spread: str
    z_spread: str
    benchmark_spread: str
    market_value: str
    book_value: str
    clean_price: str
    dirty_price: str
    accrued_interest: str
    duration: str
    modified_duration: str
    convexity: str
    dv01: str
    pvbp: str
