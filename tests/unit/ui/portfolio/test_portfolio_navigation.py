from __future__ import annotations

from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.navigation.routes import Route
from aip.ui.modules.portfolio.routing.portfolio_route import PortfolioRoute


def test_portfolio_route_registers_in_navigation_manager() -> None:
    manager = NavigationManager()
    manager.register(PortfolioRoute())
    manager.register(Route("home", "Home"))

    manager.navigate("portfolio")

    assert manager.current_route() is not None
    assert manager.current_route().id == "portfolio"
