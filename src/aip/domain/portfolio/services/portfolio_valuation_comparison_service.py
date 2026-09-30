from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ValuationComparisonInput:
    identity: str
    issuer: str
    currency: str
    market_value: Decimal | None
    book_value: Decimal | None
    source_reference: str


@dataclass(frozen=True, slots=True)
class ValuationComparisonRow:
    source: ValuationComparisonInput
    difference: Decimal | None
    percentage: Decimal | None
    status: str


@dataclass(frozen=True, slots=True)
class ValuationComparisonTotal:
    currency: str
    market_value: Decimal | None
    book_value: Decimal | None
    difference: Decimal | None
    percentage: Decimal | None
    included_count: int
    total_count: int


@dataclass(frozen=True, slots=True)
class ValuationComparisonResult:
    rows: tuple[ValuationComparisonRow, ...]
    totals: tuple[ValuationComparisonTotal, ...]


class PortfolioValuationComparisonService:
    """Compare same-cut master values without FX, coupon or impairment adjustments."""

    @staticmethod
    def calculate(
        inputs: tuple[ValuationComparisonInput, ...],
    ) -> ValuationComparisonResult:
        rows: list[ValuationComparisonRow] = []
        for item in inputs:
            market, book = item.market_value, item.book_value
            if not item.currency:
                status = "Moneda ausente"
            elif market is None or book is None:
                status = "Valor ausente o inválido"
            elif not market.is_finite() or not book.is_finite() or market < 0 or book < 0:
                status = "Valor inválido"
            else:
                rows.append(
                    ValuationComparisonRow(
                        item,
                        market - book,
                        (market - book) / book * Decimal("100") if book > 0 else None,
                        "Calculado" if book > 0 else "Calculado · porcentaje N/D (libros cero)",
                    )
                )
                continue
            rows.append(ValuationComparisonRow(item, None, None, status))

        totals: list[ValuationComparisonTotal] = []
        for currency in sorted({row.source.currency for row in rows}):
            group = [row for row in rows if row.source.currency == currency]
            included = [row for row in group if row.difference is not None]
            market_total = (
                sum(
                    (
                        row.source.market_value
                        for row in included
                        if row.source.market_value is not None
                    ),
                    Decimal("0"),
                )
                if included
                else None
            )
            book_total = (
                sum(
                    (
                        row.source.book_value
                        for row in included
                        if row.source.book_value is not None
                    ),
                    Decimal("0"),
                )
                if included
                else None
            )
            difference = (
                market_total - book_total
                if market_total is not None and book_total is not None
                else None
            )
            percentage = (
                difference / book_total * Decimal("100")
                if difference is not None and book_total is not None and book_total > 0
                else None
            )
            totals.append(
                ValuationComparisonTotal(
                    currency,
                    market_total,
                    book_total,
                    difference,
                    percentage,
                    len(included),
                    len(group),
                )
            )
        return ValuationComparisonResult(tuple(rows), tuple(totals))
