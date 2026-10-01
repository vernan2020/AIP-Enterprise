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
class PortfolioValuationBreakdown:
    label: str
    gain: Decimal
    loss: Decimal
    net: Decimal
    position_count: int


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonResult:
    rows: tuple[PortfolioValuationComparisonRow, ...]
    gain_total: Decimal
    loss_total: Decimal
    net_total: Decimal
    gain_count: int
    loss_count: int
    available_count: int
    currency_breakdown: tuple[PortfolioValuationBreakdown, ...]
    issuer_breakdown: tuple[PortfolioValuationBreakdown, ...]


class PortfolioValuationComparisonService:
    """Expose and aggregate the Master's authoritative accumulated valuation field."""

    @classmethod
    def calculate(
        cls,
        inputs: tuple[PortfolioValuationComparisonInput, ...],
    ) -> PortfolioValuationComparisonResult:
        rows = tuple(cls._map(item) for item in inputs)
        available = tuple(
            row for row in rows if row.valuation_accumulated is not None
        )
        gain_total = sum(
            (
                row.valuation_accumulated
                for row in available
                if row.valuation_accumulated is not None
                and row.valuation_accumulated > 0
            ),
            Decimal("0"),
        )
        loss_total = sum(
            (
                abs(row.valuation_accumulated)
                for row in available
                if row.valuation_accumulated is not None
                and row.valuation_accumulated < 0
            ),
            Decimal("0"),
        )
        net_total = gain_total - loss_total
        return PortfolioValuationComparisonResult(
            rows=rows,
            gain_total=gain_total,
            loss_total=loss_total,
            net_total=net_total,
            gain_count=sum(
                1
                for row in available
                if row.valuation_accumulated is not None
                and row.valuation_accumulated > 0
            ),
            loss_count=sum(
                1
                for row in available
                if row.valuation_accumulated is not None
                and row.valuation_accumulated < 0
            ),
            available_count=len(available),
            currency_breakdown=cls._breakdown(available, by="currency"),
            issuer_breakdown=cls._breakdown(available, by="issuer"),
        )

    @classmethod
    def _breakdown(
        cls,
        rows: tuple[PortfolioValuationComparisonRow, ...],
        *,
        by: str,
    ) -> tuple[PortfolioValuationBreakdown, ...]:
        buckets: dict[str, list[Decimal]] = {}
        for row in rows:
            value = row.valuation_accumulated
            if value is None:
                continue
            raw_label = getattr(row.source, by, "")
            label = str(raw_label or "").strip() or "N/D"
            buckets.setdefault(label, []).append(value)

        result = []
        for label, values in buckets.items():
            gain = sum((value for value in values if value > 0), Decimal("0"))
            loss = sum((abs(value) for value in values if value < 0), Decimal("0"))
            result.append(
                PortfolioValuationBreakdown(
                    label=label,
                    gain=gain,
                    loss=loss,
                    net=gain - loss,
                    position_count=len(values),
                )
            )
        return tuple(
            sorted(
                result,
                key=lambda item: (abs(item.net), item.position_count, item.label),
                reverse=True,
            )
        )

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
