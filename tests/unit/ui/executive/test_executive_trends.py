from __future__ import annotations

from aip.ui.modules.executive.views.executive_trends_view import ExecutiveTrendsView


def test_executive_trends_view_constructs(qt_app) -> None:
    view = ExecutiveTrendsView((("30 Days", ("1", "2")),))
    assert view is not None
