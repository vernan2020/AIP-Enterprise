from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar


class Ribbon(QToolBar):
    """Top-level navigation for the institutional AIP desktop shell.

    The ribbon owns actions only.  It never constructs workspaces or services;
    MainWindow remains the single presentation composition point.
    """

    _LABELS = (
        "Home",
        "Executive",
        "Portfolio",
        "Market",
        "Price Risk",
        "Macro Intelligence",
        "Liquidity",
        "Treasury",
        "Refresh All",
        "Reports",
        "Administration",
        "Help",
    )

    def __init__(self) -> None:
        super().__init__("Ribbon")
        self.setMovable(False)
        self.setFloatable(False)
        self._actions: dict[str, QAction] = {}
        for label in self._LABELS:
            action = QAction(label, self)
            self.addAction(action)
            self._actions[label] = action

    def action(self, label: str) -> QAction:
        """Return a registered ribbon action by its stable label."""
        return self._actions[label]
