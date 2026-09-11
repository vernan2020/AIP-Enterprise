from __future__ import annotations

from PySide6.QtWidgets import QSplitter, QTabWidget, QWidget

from aip.ui.modules.market.views.market_view import MarketView


def test_market_view_renders_and_binds(qt_app) -> None:
    view = MarketView()

    assert isinstance(view, QWidget)
    assert view.view_model().status == "loaded"
    assert view.findChild(QSplitter, "marketAnalyticalSplitter") is not None

    tabs = view.findChild(QTabWidget, "marketRelativeValueTabs")
    assert tabs is not None
    assert tabs.count() == 3
    assert tabs.tabText(0).startswith("RV Portafolio")
    assert tabs.tabText(1).startswith("RV Mercado")
    assert tabs.tabText(2).startswith("Rotación")
