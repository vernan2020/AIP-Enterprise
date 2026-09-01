from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.modules.treasury.routing.treasury_route import TreasuryRoute
from aip.ui.navigation.menu_registry import MenuRegistry
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.shell.main_window import MainWindow
from aip.ui.shell.workspace import Workspace


def test_treasury_route_and_menu_registry_integration(qt_app) -> None:
    navigation = NavigationManager()
    menu_registry = MenuRegistry()
    navigation.register(TreasuryRoute())
    menu_registry.register("treasury", "Treasury")

    navigation.navigate("treasury")

    assert navigation.current_route().id == "treasury"
    assert menu_registry.route_label("treasury") == "Treasury"


def test_main_window_opens_treasury_workspace_from_shell(qt_app) -> None:
    window = MainWindow()
    window.open_workspace("treasury")

    tab_titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]
    assert "Tesorería" in tab_titles


def test_workspace_can_open_treasury_tab(qt_app) -> None:
    workspace = Workspace()
    workspace.open_tab("Treasury", QWidget())

    assert workspace.tabText(0) == "Treasury"
