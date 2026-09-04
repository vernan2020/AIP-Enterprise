from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation


@dataclass(frozen=True, slots=True)
class LiquidityCoverageInput:
    cash_and_due_from: Decimal | None
    investments: Decimal | None
    available_investments: Decimal | None
    public_obligations: Decimal | None


@dataclass(frozen=True, slots=True)
class LiquidityCoverageCalculation:
    value: Decimal | None
    complete: bool
    missing_components: tuple[str, ...] = ()


class LiquidityCoverageCalculator:
    """Calcula la razón de liquidez definida por 08ME14-01.

    Fórmula institucional:
        (11000000 + 12000000 + 12500000) / 21000000

    Ningún componente faltante se interpreta como cero.
    """

    def calculate(self, data: LiquidityCoverageInput) -> LiquidityCoverageCalculation:
        components = {
            "11000000": data.cash_and_due_from,
            "12000000": data.investments,
            "12500000": data.available_investments,
            "21000000": data.public_obligations,
        }
        missing = tuple(code for code, value in components.items() if value is None)
        if missing:
            return LiquidityCoverageCalculation(
                value=None,
                complete=False,
                missing_components=missing,
            )
        denominator = data.public_obligations
        if denominator == Decimal("0"):
            return LiquidityCoverageCalculation(value=None, complete=False)
        numerator = (
            (data.cash_and_due_from or Decimal("0"))
            + (data.investments or Decimal("0"))
            + (data.available_investments or Decimal("0"))
        )
        try:
            value = numerator / denominator
        except (DivisionByZero, InvalidOperation):
            return LiquidityCoverageCalculation(value=None, complete=False)
        return LiquidityCoverageCalculation(value=value, complete=True)
