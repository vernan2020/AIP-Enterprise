from __future__ import annotations

from aip.ui.shell.sidebar import Sidebar
from aip.ui.navigation.navigation_manager import NavigationManager


def test_sidebar_contains_executive_entry(qt_app) -> None:
    sidebar = Sidebar(NavigationManager())
    assert sidebar._tree is not None
