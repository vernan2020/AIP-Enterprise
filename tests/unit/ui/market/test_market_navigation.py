from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.modules.market.routing.market_route import MarketRoute
from aip.ui.navigation.menu_registry import MenuRegistry
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.shell.main_window import MainWindow
from aip.ui.shell.workspace import Workspace


def test_market_route_and_menu_registry_integration(qt_app) -> None:
    navigation = NavigationManager()
    menu_registry = MenuRegistry()
    navigation.register(MarketRoute())
    menu_registry.register("market", "Market")
    navigation.navigate("market")

    assert navigation.current_route().id == "market"
    assert menu_registry.route_label("market") == "Market"


def test_main_window_opens_market_workspace_from_shell(qt_app) -> None:
    window = MainWindow()
    window.open_workspace("market")

    tab_titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]
    assert "Mercado" in tab_titles


def test_workspace_can_open_market_tab(qt_app) -> None:
    workspace = Workspace()
    workspace.open_tab("Market", QWidget())
    assert workspace.count() == 1
