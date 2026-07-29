from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioRow:
    isin: str
    issuer: str
    instrument: str
    currency: str
    nominal: str
    market_value: str
    book_value: str
    yield_value: str
    modified_duration: str
    classification: str
    hqla_status: str
    mil_status: str
    recommendation: str
