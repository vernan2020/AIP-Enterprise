from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
    FinancialAnalysisPresenter,
)
from aip.domain.financial_analysis.models import (
    FinancialAnalysisSnapshot,
    FinancialEntity,
    FinancialMetricHistoryPoint,
    FinancialMetricHistorySeries,
)


ENTITY = FinancialEntity("3004045138", "COOPEALIANZA R.L.")


def test_presenter_maps_money_history_to_millions_and_window_change() -> None:
    snapshot = FinancialAnalysisSnapshot(
        status="AVAILABLE",
        cutoff_date=date(2026, 7, 31),
        selected_entity=ENTITY,
        entities=(ENTITY,),
        available_dates=(date(2026, 7, 31),),
        metric_history=(
            FinancialMetricHistorySeries(
                code="ASSETS",
                label="Activos",
                unit="CRC",
                source_account="10000",
                points=(
                    FinancialMetricHistoryPoint(date(2026, 6, 30), Decimal("800000000000")),
                    FinancialMetricHistoryPoint(date(2026, 7, 31), Decimal("840000000000")),
                ),
            ),
        ),
    )

    view_model = FinancialAnalysisPresenter._from_snapshot(snapshot)

    series = view_model.metric_history[0]
    assert series.unit == "₡ MM"
    assert series.latest_value == "₡840,000.00 MM"
    assert series.period_change == "+5.00% en la ventana"
    assert series.available_points == 2
    assert series.points[0].value == 800000.0
    assert series.points[1].date_label == "07/2026"


def test_presenter_maps_percent_history_change_in_percentage_points() -> None:
    snapshot = FinancialAnalysisSnapshot(
        status="AVAILABLE",
        cutoff_date=date(2026, 7, 31),
        selected_entity=ENTITY,
        entities=(ENTITY,),
        available_dates=(date(2026, 7, 31),),
        metric_history=(
            FinancialMetricHistorySeries(
                code="ROA",
                label="ROA",
                unit="PERCENT",
                source_account="81000",
                points=(
                    FinancialMetricHistoryPoint(date(2026, 5, 31), Decimal("0.90")),
                    FinancialMetricHistoryPoint(date(2026, 6, 30), None),
                    FinancialMetricHistoryPoint(date(2026, 7, 31), Decimal("1.05")),
                ),
            ),
        ),
    )

    view_model = FinancialAnalysisPresenter._from_snapshot(snapshot)

    series = view_model.metric_history[0]
    assert series.unit == "%"
    assert series.latest_value == "1.05%"
    assert series.period_change == "+0.15 pp en la ventana"
    assert series.available_points == 2
    assert series.total_points == 3
    assert series.points[1].value is None
    assert series.points[1].display_value == "-"
