from __future__ import annotations

from aip.ui.navigation.routes import Route


class TreasuryRoute(Route):
    """Navigation route for the treasury workspace."""

    def __init__(self) -> None:
        super().__init__("treasury", "Treasury", "treasury")
