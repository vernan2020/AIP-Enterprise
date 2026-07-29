from __future__ import annotations

from aip.ui.modules.executive.widgets.executive_donut_chart import ExecutiveDonutChart
from aip.ui.modules.executive.widgets.executive_summary_table import ExecutiveSummaryTable
from aip.ui.modules.executive.widgets.executive_trend_chart import ExecutiveTrendChart


def test_executive_charts_and_tables_construct(qt_app) -> None:
    chart = ExecutiveTrendChart("Line", ("1", "2"))
    donut = ExecutiveDonutChart("Donut", "50")
    table = ExecutiveSummaryTable(("A", "B"))
    assert chart is not None
    assert donut is not None
    assert table is not None
