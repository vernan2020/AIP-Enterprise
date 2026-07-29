from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar


class Ribbon(QToolBar):
    """Top ribbon with grouped navigation actions."""

    def __init__(self) -> None:
        super().__init__("Ribbon")
        self.setMovable(False)
        self.setFloatable(False)
        self._actions: dict[str, QAction] = {}
        for label in ["Home", "Portfolio", "Market", "Liquidity", "Treasury", "Executive", "Reports", "Administration", "Help"]:
            action = QAction(label, self)
            self.addAction(action)
            self._actions[label] = action

    def action(self, label: str) -> QAction:
        return self._actions[label]
