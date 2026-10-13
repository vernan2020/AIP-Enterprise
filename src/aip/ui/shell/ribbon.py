from __future__ import annotations

import base64

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFontMetrics, QPixmap
from PySide6.QtWidgets import QLabel, QMenu, QSizePolicy, QToolBar, QToolButton, QWidget

from aip.ui.assets import COOPEALIANZA_LOGO_PNG_BASE64


class Ribbon(QToolBar):
    """Header de navegación compacto y corporativo de AIP Enterprise 2.0."""

    _LABELS = (
        "Inicio",
        "Ejecutivo",
        "Portafolio",
        "Mercado",
        "Riesgo de Precio",
        "Riesgo de Tasas · RTILB",
        "Inteligencia Macroeconómica",
        "Liquidez",
        "Tesorería",
        "Análisis Financiero",
        "Agente IA",
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
        self.setMinimumHeight(52)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._actions: dict[str, QAction] = {}
        self._overflow_actions: dict[str, QAction] = {}

        self._brand_logo = self._build_brand_logo()
        self.addWidget(self._brand_logo)
        self.addSeparator()

        for index, label in enumerate(self._LABELS):
            if index in {4, 11, 12}:
                self.addSeparator()
            action = QAction(label, self)
            self.addAction(action)
            action.setToolTip(f"Abrir {label}")
            self._actions[label] = action

        spacer = QWidget(self)
        spacer.setObjectName("ribbonFlexibleSpacer")
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self._overflow_menu = QMenu(self)
        self._overflow_button = QToolButton(self)
        self._overflow_button.setObjectName("aipRibbonMoreModules")
        self._overflow_button.setText("Más módulos ▾")
        self._overflow_button.setToolTip("Ver módulos que no caben en la barra de navegación")
        self._overflow_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._overflow_button.setMenu(self._overflow_menu)
        for label, action in self._actions.items():
            menu_action = QAction(label, self._overflow_menu)
            menu_action.triggered.connect(action.trigger)
            self._overflow_menu.addAction(menu_action)
            self._overflow_actions[label] = menu_action
        self.addWidget(self._overflow_button)
        self._overflow_button.hide()

        self.setStyleSheet(
            "QToolBar#aipRibbon {background:#FFFFFF; border:none; "
            "border-bottom:1px solid #D5DEE3; spacing:1px; padding:3px 8px;}"
            "QToolBar#aipRibbon QToolButton {background:transparent; border:none; "
            "border-radius:6px; padding:7px 9px; color:#354B5E; font-size:9pt; font-weight:600;}"
            "QToolBar#aipRibbon QToolButton:hover {background:#F0F8FC; color:#005EB8;}"
            "QToolBar#aipRibbon QToolButton:pressed {background:#DDEFFA; color:#00345F;}"
            "QToolBar#aipRibbon::separator {background:#D5DEE3; width:1px; margin:7px 6px;}"
            "QToolButton#aipRibbonMoreModules {background:#F0F8FC; color:#005EB8;"
            "border:1px solid #73B3DD; border-radius:7px; padding:6px 9px; font-weight:700;}"
            "QLabel#coopealianzaHeaderLogo {background:transparent; border:none; margin:0 8px 0 2px;}"
        )
        QTimer.singleShot(0, self._update_overflow)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_overflow)

    def _update_overflow(self) -> None:
        """Preserve all routes when DPI or window width limits the ribbon."""
        if not self._actions:
            return
        # Always reserve the logo, command menu, system spacing and more button.
        available = max(0, self.width() - self._brand_logo.width() - 155)
        metrics = QFontMetrics(self.font())
        overflow: list[str] = []
        for label, action in self._actions.items():
            button = self.widgetForAction(action)
            estimate = button.sizeHint().width() if button is not None else 0
            required = max(estimate, metrics.horizontalAdvance(label) + 25)
            if available >= required:
                available -= required
                action.setVisible(True)
            else:
                action.setVisible(False)
                overflow.append(label)
        for label, menu_action in self._overflow_actions.items():
            menu_action.setVisible(label in overflow)
        self._overflow_button.setVisible(bool(overflow))

    @staticmethod
    def _build_brand_logo() -> QLabel:
        label = QLabel()
        label.setObjectName("coopealianzaHeaderLogo")
        label.setFixedSize(204, 42)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setToolTip("Coopealianza R.L.")

        pixmap = QPixmap()
        payload = base64.b64decode(COOPEALIANZA_LOGO_PNG_BASE64)
        if pixmap.loadFromData(payload):
            label.setPixmap(
                pixmap.scaled(
                    194,
                    38,
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
