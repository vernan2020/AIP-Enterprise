from __future__ import annotations

from collections.abc import Iterable

from aip.ui.navigation.routes import Route


class NavigationManager:
    def __init__(self) -> None:
        self._routes: dict[str, Route] = {}
        self._current: Route | None = None

    def register(self, route: Route) -> None:
        self._routes[route.id] = route

    def register_many(self, routes: Iterable[Route]) -> None:
        for route in routes:
            self.register(route)

    def route(self, route_id: str) -> Route:
        return self._routes[route_id]

    def navigate(self, route_id: str) -> Route:
        route = self.route(route_id)
        self._current = route
        return route

    def current_route(self) -> Route | None:
        return self._current
