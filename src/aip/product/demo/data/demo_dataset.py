from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class DemoDataset:
    """Deterministic application dataset for the demo product slice."""

    valuation_date: date
    portfolio: dict[str, Any] = field(default_factory=dict)
    market: dict[str, Any] = field(default_factory=dict)
    liquidity: dict[str, Any] = field(default_factory=dict)
    treasury: dict[str, Any] = field(default_factory=dict)
    executive: dict[str, Any] = field(default_factory=dict)
    status: dict[str, Any] = field(default_factory=dict)
