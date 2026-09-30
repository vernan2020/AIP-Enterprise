from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonInput:
    identity: str
    issuer: str
    currency: str
    valuation_accumulated: Decimal | None
    source_reference: str


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonRow:
    source: PortfolioValuationComparisonInput
    valuation_accumulated: Decimal | None
    status: str


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonResult:
    rows: tuple[PortfolioValuationComparisonRow, ...]


class PortfolioValuationComparisonService:
    """Expose the master accumulated valuation field without deriving gain/loss."""

    @classmethod
    def calculate(
        cls,
        inputs: tuple[PortfolioValuationComparisonInput, ...],
    ) -> PortfolioValuationComparisonResult:
        return PortfolioValuationComparisonResult(rows=tuple(cls._map(item) for item in inputs))

    @staticmethod
    def _map(item: PortfolioValuationComparisonInput) -> PortfolioValuationComparisonRow:
        if item.valuation_accumulated is None:
            return PortfolioValuationComparisonRow(
                source=item,
                valuation_accumulated=None,
                status="Valuacion acumulada ausente o invalida",
            )
        return PortfolioValuationComparisonRow(
            source=item,
            valuation_accumulated=item.valuation_accumulated,
            status="Maestro de Inversiones",
        )
