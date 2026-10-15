"""Actions for real portfolio data, with no placeholder commands."""

from __future__ import annotations

from PySide6.QtWidgets import QToolBar


class PortfolioToolbar(QToolBar):
    def __init__(self) -> None:
        super().__init__("Portafolio")
        self.setMovable(False)
        self.setFloatable(False)
        self.setObjectName("portfolioActions")
        self.refresh_action = self.addAction("Actualizar")
        self.export_action = self.addAction("Exportar CSV")
        self.reset_action = self.addAction("Limpiar filtros")
        self.setStyleSheet(
            "QToolBar#portfolioActions {background:#FFFFFF;"
            "border:1px solid #D2E2ED; border-radius:8px; spacing:8px; padding:4px;}"
            "QToolBar#portfolioActions QToolButton {color:#00549F; font-weight:700;"
            "font-size:10pt; border:1px solid #BBD5E6; border-radius:6px;"
            "padding:7px 12px; background:#F4F9FD;}"
            "QToolBar#portfolioActions QToolButton:hover {background:#DDEFFC;}"
        )
