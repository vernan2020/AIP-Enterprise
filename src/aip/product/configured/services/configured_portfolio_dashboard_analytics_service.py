from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable


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

    @property
    def maturity_buckets(self) -> tuple[PortfolioDashboardBreakdown, ...]:
        """Alias semántico: los tramos representan vencimiento contractual."""

        return self.duration_buckets


class ConfiguredPortfolioDashboardAnalyticsService:
    """Analítica determinística del panel de Portafolio.

    La duración modificada y el plazo contractual son métricas distintas. Los
    tramos del panel se construyen exclusivamente con fecha de vencimiento
    contractual (o, como respaldo explícito, ``days_to_maturity``). La duración
    modificada permanece como KPI separado y nunca se utiliza para inferir el
    vencimiento de un título.
    """

    _DAYS_IN_ONE_YEAR = 365
    _DAYS_IN_FIVE_YEARS = 365 * 5

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

    @staticmethod
    def _date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        for candidate in (text, text[:10]):
            try:
                return date.fromisoformat(candidate)
            except ValueError:
                continue
        for pattern in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _integer(value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(Decimal(str(value)))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _breakdown(
        cls,
        positions: list[dict[str, Any]],
        *,
        key_resolver: Callable[[dict[str, Any]], str],
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
        order = {
            "< 1 año": 0,
            "1 a 5 años": 1,
            "> 5 años": 2,
            "Vencido": 3,
            "N/D": 4,
        }
        rows.sort(
            key=lambda item: (
                order.get(item.label, 99),
                -item.market_value_crc,
            )
            if item.label in order
            else (99, -item.market_value_crc)
        )
        if not any(item.label in order for item in rows):
            rows.sort(key=lambda item: item.market_value_crc, reverse=True)
        return tuple(rows)

    @classmethod
    def _maturity_bucket(
        cls,
        position: dict[str, Any],
        *,
        valuation_date: date | None,
    ) -> str:
        maturity = cls._date(position.get("maturity_date"))
        if maturity is not None and valuation_date is not None:
            days_to_maturity = (maturity - valuation_date).days
        else:
            days_to_maturity = cls._integer(position.get("days_to_maturity"))

        if days_to_maturity is None:
            return "N/D"
        if days_to_maturity < 0:
            return "Vencido"
        if days_to_maturity <= cls._DAYS_IN_ONE_YEAR:
            return "< 1 año"
        if days_to_maturity <= cls._DAYS_IN_FIVE_YEARS:
            return "1 a 5 años"
        return "> 5 años"

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
            key_resolver=lambda item: str(item.get("issuer") or "N/D"),
            total_market_value=total,
        )
        currency_rows = cls._breakdown(
            positions,
            key_resolver=lambda item: str(item.get("currency") or "N/D").upper(),
            total_market_value=total,
        )

        valuation_date = cls._date(portfolio.get("valuation_date"))
        maturity_rows = cls._breakdown(
            positions,
            key_resolver=lambda item: cls._maturity_bucket(
                item,
                valuation_date=valuation_date,
            ),
            total_market_value=total,
        )

        hhi = sum(
            ((row.share_percent / Decimal("100")) ** 2 for row in issuer_rows),
            start=Decimal("0"),
        ) * Decimal("10000")

        opportunity_rows: list[PortfolioOpportunityPoint] = []
        if market is not None:
            candidates = market.get("portfolio_relative_value_results")
            if not isinstance(candidates, (tuple, list)):
                candidates = market.get("pricing_results", ())
            for item in candidates:
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
            duration_buckets=maturity_rows,
            opportunities=tuple(opportunity_rows[:10]),
        )
