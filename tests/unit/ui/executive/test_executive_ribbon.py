from __future__ import annotations

from aip.ui.shell.ribbon import Ribbon


def test_ribbon_contains_executive_action(qt_app) -> None:
    ribbon = Ribbon()
    assert ribbon.action("Executive") is not None
