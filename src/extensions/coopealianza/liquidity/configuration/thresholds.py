from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Immutable thresholds for institutional liquidity policy evaluation."""

    warning_limit: Decimal | None = None
    blocking_limit: Decimal | None = None
