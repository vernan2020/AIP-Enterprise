from __future__ import annotations

from aip.ui.navigation.routes import Route


class MarketRoute(Route):
    """Navigation route for the market workspace."""

    def __init__(self) -> None:
        super().__init__("market", "Market", "market")
