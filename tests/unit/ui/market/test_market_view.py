from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.modules.market.views.market_view import MarketView


def test_market_view_renders_and_binds(qt_app) -> None:
    view = MarketView()
    assert isinstance(view, QWidget)
    assert view.view_model().status == "loaded"
