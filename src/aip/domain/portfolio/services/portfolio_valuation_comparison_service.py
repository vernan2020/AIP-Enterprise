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
class PortfolioValuationContribution:
    label: str
    gain: Decimal = Decimal("0")
    loss: Decimal = Decimal("0")

    @property
    def net(self) -> Decimal:
        return self.gain + self.loss


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonResult:
    rows: tuple[PortfolioValuationComparisonRow, ...]
    gain_total: Decimal
    loss_total: Decimal
    net_total: Decimal
    gain_count: int
    loss_count: int
    top_gains: tuple[PortfolioValuationComparisonRow, ...]
    top_losses: tuple[PortfolioValuationComparisonRow, ...]
    currency_contributions: tuple[PortfolioValuationContribution, ...]
    issuer_contributions: tuple[PortfolioValuationContribution, ...]
    top_positions: tuple[PortfolioValuationComparisonRow, ...]


class PortfolioValuationComparisonService:
    """Expose and aggregate the Master's accumulated valuation without deriving gain/loss."""

    @classmethod
    def calculate(
        cls,
        inputs: tuple[PortfolioValuationComparisonInput, ...],
    ) -> PortfolioValuationComparisonResult:
        rows = tuple(cls._map(item) for item in inputs)
        available = tuple(
            row
            for row in rows
            if row.valuation_accumulated is not None and row.valuation_accumulated.is_finite()
        )

        gains = tuple(row for row in available if row.valuation_accumulated > 0)
        losses = tuple(row for row in available if row.valuation_accumulated < 0)

        gain_total = sum(
            (row.valuation_accumulated for row in gains),
            Decimal("0"),
        )
        loss_total = sum(
            (row.valuation_accumulated for row in losses),
            Decimal("0"),
        )

        top_gains = tuple(
            sorted(
                gains,
                key=lambda row: row.valuation_accumulated,
                reverse=True,
            )[:5]
        )
        top_losses = tuple(
            sorted(
                losses,
                key=lambda row: row.valuation_accumulated,
            )[:5]
        )
        top_positions = tuple(
            sorted(
                available,
                key=lambda row: abs(row.valuation_accumulated),
                reverse=True,
            )[:10]
        )

        return PortfolioValuationComparisonResult(
            rows=rows,
            gain_total=gain_total,
            loss_total=loss_total,
            net_total=gain_total + loss_total,
            gain_count=len(gains),
            loss_count=len(losses),
            top_gains=top_gains,
            top_losses=top_losses,
            currency_contributions=cls._group(available, "currency"),
            issuer_contributions=tuple(
                sorted(
                    cls._group(available, "issuer"),
                    key=lambda item: abs(item.net),
                    reverse=True,
                )[:5]
            ),
            top_positions=top_positions,
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

    @staticmethod
    def _group(
        rows: tuple[PortfolioValuationComparisonRow, ...],
        dimension: str,
    ) -> tuple[PortfolioValuationContribution, ...]:
        grouped: dict[str, tuple[Decimal, Decimal]] = {}
        for row in rows:
            value = row.valuation_accumulated
            if value is None:
                continue
            raw_label = getattr(row.source, dimension, "")
            label = str(raw_label).strip() or "N/D"
            gain, loss = grouped.get(label, (Decimal("0"), Decimal("0")))
            if value > 0:
                gain += value
            elif value < 0:
                loss += value
            grouped[label] = (gain, loss)

        return tuple(
            PortfolioValuationContribution(label=label, gain=gain, loss=loss)
            for label, (gain, loss) in sorted(grouped.items())
        )
