from __future__ import annotations

from collections.abc import Iterable


class MenuRegistry:
    def __init__(self) -> None:
        self._routes: dict[str, str] = {}

    def register(self, route_id: str, label: str) -> None:
        self._routes[route_id] = label

    def register_many(self, routes: Iterable[tuple[str, str]]) -> None:
        for route_id, label in routes:
            self.register(route_id, label)

    def route_label(self, route_id: str) -> str:
        return self._routes[route_id]
