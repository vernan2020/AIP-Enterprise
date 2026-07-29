from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurvePoint:
    label: str
    value: str
    tenor: str
