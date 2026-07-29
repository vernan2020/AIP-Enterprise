from __future__ import annotations

from aip.ui.navigation.routes import Route


class ExecutiveRoute(Route):
    """Navigation route for the executive cockpit workspace."""

    def __init__(self) -> None:
        super().__init__("executive", "Executive", "executive")
