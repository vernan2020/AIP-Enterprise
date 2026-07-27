from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AnalyticsContext:
    """Immutable analytics context for reproducible calculations."""

    valuation_date: str
    base_currency: str
    market_snapshot_reference: str | None = None
    portfolio_reference: str | None = None
    configuration_version: str | None = None
    calculation_timestamp: datetime | None = None
    calculation_identifier: str | None = None
    user_or_process_reference: str | None = None
