from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.ui.modules.portfolio.models.portfolio_history_point import PortfolioHistoryPoint
from aip.ui.modules.portfolio.views.portfolio_history_view import PortfolioHistoryView
from aip.ui.modules.portfolio.widgets.portfolio_history_line_chart import (
    PortfolioHistoryLineChart,
)


def _point(cutoff: date, market_value: str) -> PortfolioHistoryPoint:
    return PortfolioHistoryPoint(
        valuation_date=cutoff,
        market_value_mm=Decimal(market_value),
        weighted_yield_percent=Decimal("5.20"),
        modified_duration=Decimal("1.46"),
        hqla_percent=Decimal("67.3"),
        dv01_mm=Decimal("35.45"),
        hhi=Decimal("3799"),
        data_quality_status="HEALTHY",
    )


def test_history_comparisons_use_previous_calendar_month_and_december_close() -> None:
    december = _point(date(2025, 12, 31), "312000")
    july_early = _point(date(2026, 7, 15), "303000")
    july_close = _point(date(2026, 7, 31), "305000")
    august = _point(date(2026, 8, 31), "306330")
    points = (december, july_early, july_close, august)

    previous = PortfolioHistoryView._previous_month_point(points)  # noqa: SLF001
    year_end = PortfolioHistoryView._year_end_point(points, 2025)  # noqa: SLF001

    assert previous is july_close
    assert year_end is december


def test_history_chart_calculates_absolute_and_percentage_change(qt_app) -> None:
    chart = PortfolioHistoryLineChart(
        value_formatter=lambda value: f"{value:,.2f}",
        reference_value=Decimal("3.00"),
        reference_label="Objetivo institucional ≤ 3,00",
    )

    percentage = chart._percentage_change(Decimal("110"), Decimal("100"))  # noqa: SLF001
    no_percentage = chart._percentage_change(Decimal("110"), Decimal("0"))  # noqa: SLF001
    text = chart._comparison_text(  # noqa: SLF001
        "Mes ant.",
        Decimal("110"),
        Decimal("100"),
    )

    assert percentage == Decimal("10.0")
    assert no_percentage is None
    assert "Mes ant.: +10.00 (+10.0%)" == text
    assert chart.minimumHeight() == 245
