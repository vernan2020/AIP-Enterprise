from __future__ import annotations

from PySide6.QtWidgets import QToolBar


class ExecutiveToolbar(QToolBar):
    def __init__(self) -> None:
        super().__init__("Executive")
        self.setMovable(False)
        self.setFloatable(False)
