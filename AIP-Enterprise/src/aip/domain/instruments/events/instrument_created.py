from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aip.domain.instruments.base.financial_instrument import FinancialInstrument


@dataclass(frozen=True, slots=True)
class InstrumentCreated:
    """Domain event for instrument creation."""

    instrument: FinancialInstrument
    occurred_at: datetime
