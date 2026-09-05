from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.modules.executive.routing.executive_route import ExecutiveRoute
from aip.ui.navigation.menu_registry import MenuRegistry
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.shell.main_window import MainWindow
from aip.ui.shell.workspace import Workspace


def test_executive_route_and_menu_registry_integration(qt_app) -> None:
    navigation = NavigationManager()
    menu_registry = MenuRegistry()
    navigation.register(ExecutiveRoute())
    menu_registry.register("executive", "Executive")

    navigation.navigate("executive")

    assert navigation.current_route().id == "executive"
    assert menu_registry.route_label("executive") == "Executive"


def test_main_window_opens_executive_workspace_from_shell(qt_app) -> None:
    window = MainWindow()
    window.open_workspace("executive")
    tab_titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]
    assert "Ejecutivo" in tab_titles


def test_workspace_can_open_executive_tab(qt_app) -> None:
    workspace = Workspace()
    workspace.open_tab("Executive", QWidget())
    assert workspace.tabText(0) == "Executive"
