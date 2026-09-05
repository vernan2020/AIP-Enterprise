from __future__ import annotations

from PySide6.QtWidgets import QLabel

from aip.ui.shell.ribbon import Ribbon


def test_ribbon_contains_executive_action(qt_app) -> None:
    ribbon = Ribbon()
    assert ribbon.action("Ejecutivo") is not None
    assert ribbon.findChild(QLabel, "coopealianzaHeaderLogo") is not None
