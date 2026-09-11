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
        cash_and_due_from = data.cash_and_due_from
        investments = data.investments
        available_investments = data.available_investments
        public_obligations = data.public_obligations
        components = {
            "11000000": cash_and_due_from,
            "12000000": investments,
            "12500000": available_investments,
            "21000000": public_obligations,
        }
        missing = tuple(code for code, value in components.items() if value is None)
        if (
            cash_and_due_from is None
            or investments is None
            or available_investments is None
            or public_obligations is None
        ):
            return LiquidityCoverageCalculation(
                value=None,
                complete=False,
                missing_components=missing,
            )
        if public_obligations == Decimal("0"):
            return LiquidityCoverageCalculation(value=None, complete=False)
        numerator = cash_and_due_from + investments + available_investments
        try:
            value = numerator / public_obligations
        except (DivisionByZero, InvalidOperation):
            return LiquidityCoverageCalculation(value=None, complete=False)
        return LiquidityCoverageCalculation(value=value, complete=True)
