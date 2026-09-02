from __future__ import annotations

import base64

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from aip.ui.assets.coopealianza_logo import COOPEALIANZA_LOGO_PNG_BASE64
from aip.ui.themes.dark_theme import DarkTheme
from aip.ui.themes.light_theme import LightTheme


class ThemeService:
    """Aplica el tema activo y la identidad institucional del shell.

    Mantiene una API compatible con las dos generaciones del shell recuperadas:
    ``apply(widget)`` para aplicación directa sobre un widget y ``stylesheet()`` /
    ``set_theme(name)`` para el ``MainWindow`` institucional que aplica el QSS a
    nivel de ``QApplication``.
    """

    def __init__(self) -> None:
        self._theme = LightTheme()

    def stylesheet(self) -> str:
        """Devuelve el QSS del tema activo para aplicación global."""

        return self._theme.stylesheet()

    def set_theme(self, theme_name: str) -> None:
        """Selecciona un tema por nombre estable de presentación."""

        normalized = str(theme_name).strip().casefold()
        if normalized in {"light", "claro"}:
            self.set_light()
            return
        if normalized in {"dark", "oscuro"}:
            self.set_dark()
            return
        raise ValueError(f"Tema no soportado: {theme_name!r}")

    def apply(self, widget: QWidget) -> None:
        widget.setStyleSheet(self.stylesheet())
        self._apply_coopealianza_header_branding(widget)

    @staticmethod
    def _apply_coopealianza_header_branding(widget: QWidget) -> None:
        """Inserta el logo oficial de Coopealianza en el header institucional.

        El header claro preserva el arte original del logotipo, mantiene el blanco
        como superficie predominante y utiliza Azul/Celeste/Menta Coopealianza
        como estructura y estados. El activo queda embebido en el runtime y no
        depende de rutas locales del usuario.
        """

        header = widget.findChild(QWidget, "institutionalHeader")
        if header is None:
            return

        header.setMinimumHeight(66)
        header.setStyleSheet(
            "QFrame#institutionalHeader {background:#FFFFFF; border:none; "
            "border-bottom:2px solid #00A9E0;}"
            "QFrame#institutionalHeader QLabel {background:transparent; border:none; color:#00345F;}"
            "QLabel#coopealianzaHeaderLogo {background:transparent; border:none;}"
            "QLabel#headerMode {background:#F0F8FC; border:1px solid #73B3DD; border-radius:10px; "
            "padding:4px 9px; color:#005EB8; font-size:9px; font-weight:700;}"
            "QLabel#headerStatus {background:#E2F6F1; border:1px solid #40C1AC; border-radius:10px; "
            "padding:4px 9px; color:#167A68; font-size:9px; font-weight:700;}"
            "QDateEdit {min-width:112px; padding:5px 8px; background:#FFFFFF; color:#00345F; "
            "border:1px solid #73B3DD; border-radius:5px;}"
        )

        title = header.findChild(QLabel, "headerTitle")
        if title is not None:
            title.setStyleSheet(
                "font-size:15px; font-weight:800; letter-spacing:0.7px; "
                "color:#00345F; background:transparent;"
            )
        subtitle = header.findChild(QLabel, "headerSubtitle")
        if subtitle is not None:
            subtitle.setStyleSheet(
                "font-size:8px; color:#00A9E0; letter-spacing:1px; background:transparent;"
            )
        asof = header.findChild(QLabel, "headerAsOf")
        if asof is not None:
            asof.setStyleSheet(
                "font-size:8px; color:#566D7C; font-weight:700; background:transparent;"
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
        logo.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        logo.setFixedSize(236, 48)
        logo.setPixmap(
            pixmap.scaled(
                220,
                42,
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
