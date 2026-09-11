from __future__ import annotations

from PySide6.QtWidgets import QToolBar


class PortfolioToolbar(QToolBar):
    def __init__(self) -> None:
        super().__init__("Portafolio")
        self.setMovable(False)
        self.addAction("Actualizar")
        self.addAction("Fijar")
        self.addAction("Cerrar")
