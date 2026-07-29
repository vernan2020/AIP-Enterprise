from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.modules.treasury.views.treasury_view import TreasuryView


def test_treasury_view_renders_and_binds(qt_app) -> None:
    view = TreasuryView()
    assert isinstance(view, QWidget)
    assert view.view_model().status == "loaded"
