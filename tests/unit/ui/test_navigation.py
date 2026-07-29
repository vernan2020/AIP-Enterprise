from __future__ import annotations

from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.navigation.routes import Route


def test_navigation_manager_registers_and_resolves_routes() -> None:
    manager = NavigationManager()
    manager.register(Route("home", "Home"))
    manager.register(Route("portfolio", "Portfolio"))

    assert manager.route("home").id == "home"
    assert manager.route("portfolio").label == "Portfolio"

    assert manager.current_route() is None

    manager.navigate("home")
    assert manager.current_route() is not None
    assert manager.current_route().id == "home"
