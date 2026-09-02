from __future__ import annotations

import base64

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from aip.ui.assets.coopealianza_logo import COOPEALIANZA_LOGO_PNG_BASE64
from aip.ui.themes.dark_theme import DarkTheme
from aip.ui.themes.light_theme import LightTheme


class ThemeService:
    """Aplica el tema activo y la identidad institucional del shell."""

    def __init__(self) -> None:
        self._theme = LightTheme()

    def apply(self, widget: QWidget) -> None:
        widget.setStyleSheet(self._theme.stylesheet())
        self._apply_coopealianza_header_branding(widget)

    @staticmethod
    def _apply_coopealianza_header_branding(widget: QWidget) -> None:
        """Inserta el logo oficial de Coopealianza en el header institucional.

        El PNG se carga desde un activo embebido del runtime para que la interfaz
        no dependa de una ruta local. Se conserva el arte original sobre una
        placa blanca y el fondo del header utiliza el Azul Coopealianza oficial.
        """

        header = widget.findChild(QWidget, "institutionalHeader")
        if header is None:
            return

        header.setMinimumHeight(60)
        header.setStyleSheet(
            "QFrame#institutionalHeader {background:#005EB8; border:none; "
            "border-bottom:3px solid #00A9E0;}"
            "QFrame#institutionalHeader QLabel {background:transparent; border:none; color:#FFFFFF;}"
            "QLabel#coopealianzaHeaderLogo {background:#FFFFFF; border:1px solid #D5DEE3; "
            "border-radius:7px; padding:2px 7px;}"
            "QLabel#headerMode {background:#1675C5; border:1px solid #73B3DD; border-radius:10px; "
            "padding:4px 9px; color:#FFFFFF; font-size:9px; font-weight:700;}"
            "QLabel#headerStatus {background:#167A68; border:1px solid #40C1AC; border-radius:10px; "
            "padding:4px 9px; color:#FFFFFF; font-size:9px; font-weight:700;}"
            "QDateEdit {min-width:112px; padding:5px 8px; background:#FFFFFF; color:#00345F; "
            "border:1px solid #73B3DD; border-radius:5px;}"
        )

        if header.findChild(QLabel, "coopealianzaHeaderLogo") is not None:
            return

        layout = header.layout()
        if layout is None or not hasattr(layout, "insertWidget"):
            return

        pixmap = QPixmap()
        raw = base64.b64decode(COOPEALIANZA_LOGO_PNG_BASE64)
        if not pixmap.loadFromData(raw, "PNG"):
            return

        logo = QLabel(header)
        logo.setObjectName("coopealianzaHeaderLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(178, 44)
        logo.setPixmap(
            pixmap.scaled(
                162,
                38,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        logo.setToolTip("Coopealianza R.L.")
        layout.insertWidget(0, logo)

    def set_dark(self) -> None:
        self._theme = DarkTheme()

    def set_light(self) -> None:
        self._theme = LightTheme()

    def toggle(self) -> None:
        if isinstance(self._theme, DarkTheme):
            self.set_light()
        else:
            self.set_dark()
