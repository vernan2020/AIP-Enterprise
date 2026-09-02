from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar


class Ribbon(QToolBar):
    """Navegación superior compacta del entorno institucional AIP."""

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
        self.setToolButtonStyle(self.toolButtonStyle())
        self._actions: dict[str, QAction] = {}
        for index, label in enumerate(self._LABELS):
            if index in {4, 8, 9}:
                self.addSeparator()
            action = QAction(label, self)
            self.addAction(action)
            self._actions[label] = action
        self.setStyleSheet(
            "QToolBar#aipRibbon {background:#FFFFFF; border:none; border-bottom:1px solid #D7E0E8; "
            "spacing:2px; padding:3px 8px;}"
            "QToolBar#aipRibbon QToolButton {background:transparent; border:none; border-radius:5px; "
            "padding:6px 8px; color:#354B5E; font-size:9px;}"
            "QToolBar#aipRibbon QToolButton:hover {background:#EAF1F6; color:#174E78;}"
            "QToolBar#aipRibbon QToolButton:pressed {background:#DCE9F5; color:#174E78;}"
            "QToolBar#aipRibbon::separator {background:#D7E0E8; width:1px; margin:5px 5px;}"
        )

    def action(self, label: str) -> QAction:
        """Devuelve una acción registrada por su etiqueta estable."""
        return self._actions[label]
