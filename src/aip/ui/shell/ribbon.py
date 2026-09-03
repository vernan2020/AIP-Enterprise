from __future__ import annotations

import base64

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QToolBar, QWidget

from aip.ui.assets import COOPEALIANZA_LOGO_PNG_BASE64


class Ribbon(QToolBar):
    """Header de navegación compacto y corporativo de AIP Enterprise 2.0."""

    _LABELS = (
        "Inicio",
        "Ejecutivo",
        "Portafolio",
        "Mercado",
        "Riesgo de Precio",
        "Inteligencia Macroeconómica",
        "Liquidez",
        "Tesorería",
        "Análisis Financiero",
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
        self.setMinimumHeight(56)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._actions: dict[str, QAction] = {}

        self._brand_logo = self._build_brand_logo()
        self.addWidget(self._brand_logo)
        self.addSeparator()

        for index, label in enumerate(self._LABELS):
            if index in {4, 9, 10}:
                self.addSeparator()
            action = QAction(label, self)
            self.addAction(action)
            self._actions[label] = action

        spacer = QWidget(self)
        spacer.setObjectName("ribbonFlexibleSpacer")
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self.setStyleSheet(
            "QToolBar#aipRibbon {background:#FFFFFF; border:none; "
            "border-bottom:1px solid #D5DEE3; spacing:2px; padding:4px 10px;}"
            "QToolBar#aipRibbon QToolButton {background:transparent; border:none; "
            "border-radius:5px; padding:7px 8px; color:#354B5E; font-size:9px; font-weight:600;}"
            "QToolBar#aipRibbon QToolButton:hover {background:#F0F8FC; color:#005EB8;}"
            "QToolBar#aipRibbon QToolButton:pressed {background:#DDEFFA; color:#00345F;}"
            "QToolBar#aipRibbon::separator {background:#D5DEE3; width:1px; margin:7px 6px;}"
            "QLabel#coopealianzaHeaderLogo {background:transparent; border:none; margin:0 8px 0 2px;}"
        )

    @staticmethod
    def _build_brand_logo() -> QLabel:
        label = QLabel()
        label.setObjectName("coopealianzaHeaderLogo")
        label.setFixedSize(224, 46)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setToolTip("Coopealianza R.L.")

        pixmap = QPixmap()
        payload = base64.b64decode(COOPEALIANZA_LOGO_PNG_BASE64)
        if pixmap.loadFromData(payload, b"PNG"):
            label.setPixmap(
                pixmap.scaled(
                    214,
                    42,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            label.setText("Coopealianza")
            label.setStyleSheet(
                "color:#005EB8; font-size:16px; font-weight:800; background:transparent;"
            )
        return label

    def action(self, label: str) -> QAction:
        """Devuelve una acción registrada por su etiqueta estable."""
        return self._actions[label]
