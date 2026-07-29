from __future__ import annotations

from aip.ui.modules.executive.widgets.executive_alert_panel import ExecutiveAlertPanel
from aip.ui.modules.executive.widgets.executive_metric_card import ExecutiveMetricCard
from aip.ui.modules.executive.widgets.executive_status_card import ExecutiveStatusCard
from aip.ui.modules.executive.widgets.executive_trend_chart import ExecutiveTrendChart


def test_executive_widgets_construct(qt_app) -> None:
    panel = ExecutiveAlertPanel(())
    metric = ExecutiveMetricCard("Title", "Value")
    badge = ExecutiveStatusCard("Ready")
    chart = ExecutiveTrendChart("Range", ("1", "2"))
    assert panel is not None
    assert metric is not None
    assert badge is not None
    assert chart is not None
