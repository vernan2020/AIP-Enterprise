from __future__ import annotations

from aip.ui.navigation.routes import Route


class PortfolioRoute(Route):
    def __init__(self) -> None:
        super().__init__(id="portfolio", label="Portfolio", icon="portfolio")
