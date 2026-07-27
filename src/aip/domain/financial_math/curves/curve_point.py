from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CurvePoint:
    tenor: Decimal
    zero_rate: Decimal
