from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

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
        """Aplica la identidad visual del encabezado institucional secundario.

        El logotipo se reserva para el ribbon blanco principal. El encabezado
        secundario muestra únicamente la identidad del producto, el modo de
        ejecución, el estado y la fecha de corte.
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

        logo = header.findChild(QLabel, "coopealianzaHeaderLogo")
        if logo is not None:
            logo.hide()

    def set_dark(self) -> None:
        self._theme = DarkTheme()

    def set_light(self) -> None:
        self._theme = LightTheme()

    def toggle(self) -> None:
        if isinstance(self._theme, DarkTheme):
            self.set_light()
        else:
            self.set_dark()
