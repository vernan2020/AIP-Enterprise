from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCharts import QChartView, QLineSeries
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QLabel

from aip.domain.financial_analysis.models import (
    FinancialAnalysisSnapshot,
    FinancialEntity,
    FinancialMetricHistoryPoint,
    FinancialMetricHistorySeries,
)
from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialMetricHistoryPointView,
    FinancialMetricHistorySeriesView,
)
from aip.ui.modules.financial_analysis.views.financial_history_panel import (
    FinancialHistoryPanel,
)

ENTITY = FinancialEntity("3004045138", "COOPEALIANZA R.L.")


def _present(snapshot: FinancialAnalysisSnapshot):
    from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
        FinancialAnalysisPresenter,
    )

    return FinancialAnalysisPresenter._from_snapshot(snapshot)


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

    view_model = _present(snapshot)

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

    view_model = _present(snapshot)

    series = view_model.metric_history[0]
    assert series.unit == "%"
    assert series.latest_value == "1.05%"
    assert series.period_change == "+0.15 pp en la ventana"
    assert series.available_points == 2
    assert series.total_points == 3
    assert series.points[1].value is None
    assert series.points[1].display_value == "-"


def test_historical_kpi_charts_reflow_without_recreating_data(qt_app) -> None:
    series = tuple(
        FinancialMetricHistorySeriesView(
            code=code,
            label=label,
            unit="%",
            latest_value="1.25%",
            period_change="+0.15 pp",
            source_account="SUGEF 81000",
            available_points=2,
            total_points=2,
            points=(
                FinancialMetricHistoryPointView(
                    iso_date="2026-08-31",
                    date_label="08/2026",
                    value=1.10,
                    display_value="1.10%",
                ),
                FinancialMetricHistoryPointView(
                    iso_date="2026-09-30",
                    date_label="09/2026",
                    value=1.25,
                    display_value="1.25%",
                ),
            ),
        )
        for code, label in (("ROA", "ROA"), ("ROE", "ROE"), ("SP", "Suficiencia"))
    )
    panel = FinancialHistoryPanel()
    try:
        panel.bind_history(series)
        cards = panel._history_cards
        assert len(cards) == 3
        assert len({id(card) for card in cards}) == 3

        for width, columns in ((1200, 2), (700, 1), (1200, 2)):
            panel._reflow_history_cards(width)
            assert panel._history_columns == columns
            for index, card in enumerate(cards):
                cell = panel._grid.itemAtPosition(index // columns, index % columns)
                assert cell is not None
                assert cell.widget() is card
        assert panel._history_cards == cards
    finally:
        panel.close()
        qt_app.processEvents()


def test_history_chart_readout_shows_real_monthly_values_and_clears(qt_app) -> None:
    item = FinancialMetricHistorySeriesView(
        code="ROA",
        label="ROA",
        unit="%",
        latest_value="1.25%",
        period_change="+0.15 pp",
        source_account="81000",
        available_points=2,
        total_points=3,
        points=(
            FinancialMetricHistoryPointView(
                iso_date="2026-07-31",
                date_label="07/2026",
                value=1.10,
                display_value="1.10%",
            ),
            FinancialMetricHistoryPointView(
                iso_date="2026-08-31",
                date_label="08/2026",
                value=None,
                display_value="-",
            ),
            FinancialMetricHistoryPointView(
                iso_date="2026-09-30",
                date_label="09/2026",
                value=1.25,
                display_value="1.25%",
            ),
        ),
    )
    panel = FinancialHistoryPanel()
    try:
        panel.bind_history((item,))
        labels = panel.findChildren(QLabel, "financialHistoryHoverReadout")
        assert len(labels) == 1
        readout = labels[0]
        assert "Pase el cursor" in readout.text()
        charts = panel.findChildren(QChartView)
        assert len(charts) == 1
        lines = tuple(
            series for series in charts[0].chart().series() if isinstance(series, QLineSeries)
        )
        assert len(lines) == 2

        point = lines[0].at(0)
        lines[0].hovered.emit(QPointF(point.x(), point.y()), True)
        assert "ROA" in readout.text()
        assert "07/2026" in readout.text()
        assert "1.10%" in readout.text()

        second_point = lines[1].at(0)
        lines[1].hovered.emit(QPointF(second_point.x(), second_point.y()), True)
        assert "09/2026" in readout.text()
        assert "1.25%" in readout.text()
        lines[1].hovered.emit(QPointF(second_point.x(), second_point.y()), False)
        assert "Pase el cursor" in readout.text()
    finally:
        panel.close()
        qt_app.processEvents()
