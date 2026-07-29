from __future__ import annotations

from PySide6.QtWidgets import QToolBar


class MarketToolbar(QToolBar):
    """Toolbar for the market workspace."""

    def __init__(self) -> None:
        super().__init__("Market")
