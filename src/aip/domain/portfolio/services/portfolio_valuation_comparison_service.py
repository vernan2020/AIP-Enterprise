from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonInput:
    identity: str
    issuer: str
    currency: str
    market_value: Decimal | None
    book_value: Decimal | None
    source_reference: str


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonRow:
    source: PortfolioValuationComparisonInput
    difference: Decimal | None
    percentage: Decimal | None
    status: str


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonTotal:
    currency: str
    market_value: Decimal
    book_value: Decimal
    difference: Decimal
    percentage: Decimal | None
    included_count: int
    total_count: int


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonResult:
    rows: tuple[PortfolioValuationComparisonRow, ...]
    totals: tuple[PortfolioValuationComparisonTotal, ...]


class PortfolioValuationComparisonService:
    """Compare market and book values without mixing currencies or zero-filling gaps."""

    @classmethod
    def calculate(
        cls,
        inputs: tuple[PortfolioValuationComparisonInput, ...],
    ) -> PortfolioValuationComparisonResult:
        rows = tuple(cls._compare(item) for item in inputs)
        totals = cls._aggregate(rows)
        return PortfolioValuationComparisonResult(rows=rows, totals=totals)

    @staticmethod
    def _compare(item: PortfolioValuationComparisonInput) -> PortfolioValuationComparisonRow:
        if not item.currency.strip():
            return PortfolioValuationComparisonRow(
                source=item,
                difference=None,
                percentage=None,
                status="Moneda ausente",
            )
        if item.market_value is None or item.book_value is None:
            return PortfolioValuationComparisonRow(
                source=item,
                difference=None,
                percentage=None,
                status="Valor ausente o inválido",
            )

        difference = item.market_value - item.book_value
        percentage = (
            difference / abs(item.book_value) * Decimal("100")
            if item.book_value != 0
            else None
        )
        return PortfolioValuationComparisonRow(
            source=item,
            difference=difference,
            percentage=percentage,
            status="Calculado",
        )

    @staticmethod
    def _aggregate(
        rows: tuple[PortfolioValuationComparisonRow, ...],
    ) -> tuple[PortfolioValuationComparisonTotal, ...]:
        grouped: dict[str, list[PortfolioValuationComparisonRow]] = defaultdict(list)
        for row in rows:
            grouped[row.source.currency.strip().upper() or "N/D"].append(row)

        totals: list[PortfolioValuationComparisonTotal] = []
        for currency in sorted(grouped):
            group = grouped[currency]
            included = [
                row
                for row in group
                if row.source.market_value is not None
                and row.source.book_value is not None
                and row.source.currency.strip()
            ]
            market_value = sum(
                (row.source.market_value for row in included if row.source.market_value is not None),
                Decimal("0"),
            )
            book_value = sum(
                (row.source.book_value for row in included if row.source.book_value is not None),
                Decimal("0"),
            )
            difference = market_value - book_value
            percentage = (
                difference / abs(book_value) * Decimal("100")
                if book_value != 0 and included
                else None
            )
            totals.append(
                PortfolioValuationComparisonTotal(
                    currency=currency,
                    market_value=market_value,
                    book_value=book_value,
                    difference=difference,
                    percentage=percentage,
                    included_count=len(included),
                    total_count=len(group),
                )
            )
        return tuple(totals)
