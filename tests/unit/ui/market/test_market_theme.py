from __future__ import annotations

from aip.ui.modules.market.views.market_view import MarketView
from aip.ui.services.theme_service import ThemeService


def test_theme_switching_updates_market_view(qt_app) -> None:
    view = MarketView()
    service = ThemeService()
    service.set_dark()
    service.apply(view)
    assert view.styleSheet() != ""

    service.set_light()
    service.apply(view)
    assert view.styleSheet() != ""
