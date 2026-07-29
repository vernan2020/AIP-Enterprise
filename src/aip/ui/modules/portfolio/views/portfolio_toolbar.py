from __future__ import annotations

from PySide6.QtWidgets import QToolBar, QWidget


class PortfolioToolbar(QToolBar):
    def __init__(self) -> None:
        super().__init__("Portfolio")
        self.setMovable(False)
        self.addAction("Refresh")
        self.addAction("Pin")
        self.addAction("Close")
