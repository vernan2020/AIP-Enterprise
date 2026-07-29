from __future__ import annotations

from aip.ui.modules.executive.widgets.executive_alert_panel import ExecutiveAlertPanel


def test_executive_alerts_panel_constructs(qt_app) -> None:
    panel = ExecutiveAlertPanel(())
    assert panel is not None
