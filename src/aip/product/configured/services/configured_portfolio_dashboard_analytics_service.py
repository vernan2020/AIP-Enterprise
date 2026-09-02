from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class PortfolioDashboardBreakdown:
    label: str
    market_value_crc: Decimal
    share_percent: Decimal
    position_count: int


@dataclass(frozen=True, slots=True)
class PortfolioOpportunityPoint:
    series: str
    issuer: str
    spread_bp: Decimal
    classification: str


@dataclass(frozen=True, slots=True)
class PortfolioDashboardAnalytics:
    hhi: Decimal
    top_issuers: tuple[PortfolioDashboardBreakdown, ...]
    currencies: tuple[PortfolioDashboardBreakdown, ...]
    duration_buckets: tuple[PortfolioDashboardBreakdown, ...]
    opportunities: tuple[PortfolioOpportunityPoint, ...]


class ConfiguredPortfolioDashboardAnalyticsService:
    """Deterministic portfolio dashboard analytics outside the presentation layer."""

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None or value == "":
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (TypeError, ValueError):
            return Decimal("0")

    @classmethod
    def _breakdown(
        cls,
        positions: list[dict[str, Any]],
        *,
        key_resolver,
        total_market_value: Decimal,
    ) -> tuple[PortfolioDashboardBreakdown, ...]:
        totals: dict[str, Decimal] = defaultdict(Decimal)
        counts: dict[str, int] = defaultdict(int)
        for position in positions:
            label = str(key_resolver(position) or "N/D")
            totals[label] += cls._decimal(position.get("market_value_crc"))
            counts[label] += 1
        rows = [
            PortfolioDashboardBreakdown(
                label=label,
                market_value_crc=value,
                share_percent=(
                    value / total_market_value * Decimal("100")
                    if total_market_value > 0
                    else Decimal("0")
                ),
                position_count=counts[label],
            )
            for label, value in totals.items()
        ]
        rows.sort(key=lambda item: item.market_value_crc, reverse=True)
        return tuple(rows)

    @classmethod
    def calculate(
        cls,
        *,
        portfolio: dict[str, Any],
        market: dict[str, Any] | None = None,
    ) -> PortfolioDashboardAnalytics:
        positions = [
            item for item in portfolio.get("positions", ()) if isinstance(item, dict)
        ]
        total = sum(
            (cls._decimal(position.get("market_value_crc")) for position in positions),
            start=Decimal("0"),
        )
        issuer_rows = cls._breakdown(
            positions,
            key_resolver=lambda item: item.get("issuer"),
            total_market_value=total,
        )
        currency_rows = cls._breakdown(
            positions,
            key_resolver=lambda item: str(item.get("currency") or "N/D").upper(),
            total_market_value=total,
        )

        def duration_bucket(position: dict[str, Any]) -> str:
            duration = cls._decimal(position.get("modified_duration"))
            if duration < Decimal("1"):
                return "< 1 año"
            if duration <= Decimal("5"):
                return "1 a 5 años"
            return "> 5 años"

        duration_rows = cls._breakdown(
            positions,
            key_resolver=duration_bucket,
            total_market_value=total,
        )
        hhi = sum(
            ((row.share_percent / Decimal("100")) ** 2 for row in issuer_rows),
            start=Decimal("0"),
        ) * Decimal("10000")

        opportunity_rows: list[PortfolioOpportunityPoint] = []
        if market is not None:
            for item in market.get("pricing_results", ()):
                if not isinstance(item, dict) or item.get("spread_bp") is None:
                    continue
                opportunity_rows.append(
                    PortfolioOpportunityPoint(
                        series=str(item.get("series") or item.get("instrument") or ""),
                        issuer=str(item.get("issuer") or ""),
                        spread_bp=cls._decimal(item.get("spread_bp")),
                        classification=str(item.get("classification") or ""),
                    )
                )
        opportunity_rows.sort(key=lambda item: item.spread_bp, reverse=True)
        return PortfolioDashboardAnalytics(
            hhi=hhi,
            top_issuers=issuer_rows[:10],
            currencies=currency_rows,
            duration_buckets=duration_rows,
            opportunities=tuple(opportunity_rows[:10]),
        )
