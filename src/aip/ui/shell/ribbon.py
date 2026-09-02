from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar


class Ribbon(QToolBar):
    """Navegación superior compacta de AIP Enterprise."""

    _LABELS = (
        "Inicio",
        "Ejecutivo",
        "Portafolio",
        "Mercado",
        "Riesgo de Precio",
        "Inteligencia Macroeconómica",
        "Liquidez",
        "Tesorería",
        "Actualizar Todo",
        "Reportes",
        "Administración",
        "Ayuda",
    )

    def __init__(self) -> None:
        super().__init__("Navegación")
        self.setObjectName("aipRibbon")
        self.setMovable(False)
        self.setFloatable(False)
        self._actions: dict[str, QAction] = {}
        for index, label in enumerate(self._LABELS):
            if index in {4, 8, 9}:
                self.addSeparator()
            action = QAction(label, self)
            self.addAction(action)
            self._actions[label] = action
        self.setStyleSheet(
            "QToolBar#aipRibbon {background:#FFFFFF; border:none; "
            "border-bottom:1px solid #D5DEE3; spacing:1px; padding:2px 7px;}"
            "QToolBar#aipRibbon QToolButton {background:transparent; border:none; "
            "border-radius:4px; padding:6px 8px; color:#566D7C; font-size:9px; font-weight:600;}"
            "QToolBar#aipRibbon QToolButton:hover {background:#F0F8FC; color:#005EB8;}"
            "QToolBar#aipRibbon QToolButton:pressed {background:#DDEFFA; color:#00345F;}"
            "QToolBar#aipRibbon::separator {background:#D5DEE3; width:1px; margin:5px;}"
        )

    def action(self, label: str) -> QAction:
        return self._actions[label]
