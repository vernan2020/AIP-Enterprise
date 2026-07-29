from __future__ import annotations

from PySide6.QtWidgets import QToolBar


class LiquidityToolbar(QToolBar):
    def __init__(self) -> None:
        super().__init__("Liquidity")
