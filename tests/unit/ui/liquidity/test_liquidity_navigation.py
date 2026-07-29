from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.modules.liquidity.routing.liquidity_route import LiquidityRoute
from aip.ui.navigation.menu_registry import MenuRegistry
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.shell.main_window import MainWindow
from aip.ui.shell.workspace import Workspace


def test_liquidity_route_and_menu_registry_integration(qt_app) -> None:
    navigation = NavigationManager()
    menu_registry = MenuRegistry()
    navigation.register(LiquidityRoute())
    menu_registry.register("liquidity", "Liquidity")
    navigation.navigate("liquidity")

    assert navigation.current_route().id == "liquidity"
    assert menu_registry.route_label("liquidity") == "Liquidity"


def test_main_window_opens_liquidity_workspace_from_shell(qt_app) -> None:
    window = MainWindow()
    window.open_workspace("liquidity")

    tab_titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]
    assert "Liquidity" in tab_titles


def test_workspace_can_open_liquidity_tab(qt_app) -> None:
    workspace = Workspace()
    workspace.open_tab("Liquidity", QWidget())
    assert workspace.count() == 1
