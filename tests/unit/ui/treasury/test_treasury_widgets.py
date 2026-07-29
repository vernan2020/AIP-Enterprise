from __future__ import annotations

from aip.ui.modules.treasury.widgets.treasury_filter_panel import TreasuryFilterPanel
from aip.ui.modules.treasury.widgets.treasury_status_badge import TreasuryStatusBadge


def test_treasury_widgets_construct(qt_app) -> None:
    panel = TreasuryFilterPanel()
    badge = TreasuryStatusBadge("Ready")
    assert panel is not None
    assert badge is not None
