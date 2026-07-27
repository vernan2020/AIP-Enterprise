from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.exceptions import BootstrapError


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    points: tuple[CurvePoint, ...]
    residuals: tuple[Decimal, ...]


def bootstrap_zero_curve(
    instruments: list[tuple[Decimal, Decimal, Decimal]],
    *,
    valuation_date: date | None = None,
    tolerance: Decimal = Decimal("1e-6"),
) -> BootstrapResult:
    if not instruments:
        raise BootstrapError("At least one instrument is required")
    ordered = sorted(instruments, key=lambda item: item[0])
    points: list[CurvePoint] = []
    residuals: list[Decimal] = []
    for tenor, price, face_value in ordered:
        if tenor <= Decimal("0"):
            raise BootstrapError("Tenor must be positive")
        if price <= 0:
            raise BootstrapError("Price must be positive")
        if face_value <= 0:
            raise BootstrapError("Face value must be positive")
        zero_rate = (face_value / price - Decimal("1")) / tenor
        points.append(CurvePoint(tenor=tenor, zero_rate=zero_rate))
        residuals.append(abs(zero_rate))
    if max(residuals, default=Decimal("0")) > tolerance:
        raise BootstrapError("Bootstrap residual exceeds tolerance")
    return BootstrapResult(points=tuple(points), residuals=tuple(residuals))
