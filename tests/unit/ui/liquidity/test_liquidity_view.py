from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.modules.liquidity.views.liquidity_view import LiquidityView


def test_liquidity_view_renders_and_binds(qt_app) -> None:
    view = LiquidityView()
    assert isinstance(view, QWidget)
    assert view.view_model().status == "loaded"
