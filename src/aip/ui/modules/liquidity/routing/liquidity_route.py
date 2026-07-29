from __future__ import annotations

from aip.ui.navigation.routes import Route


class LiquidityRoute(Route):
    """Navigation route for the liquidity workspace."""

    def __init__(self) -> None:
        super().__init__("liquidity", "Liquidity", "liquidity")
