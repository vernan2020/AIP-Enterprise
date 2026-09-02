from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.themes.dark_theme import DarkTheme
from aip.ui.themes.light_theme import LightTheme


class ThemeService:
    """Aplica el tema activo y los acabados institucionales del shell."""

    def __init__(self) -> None:
        self._theme = LightTheme()

    def apply(self, widget: QWidget) -> None:
        widget.setStyleSheet(self._theme.stylesheet())
        if isinstance(self._theme, LightTheme):
            self._apply_light_shell_branding(widget)

    @staticmethod
    def _apply_light_shell_branding(widget: QWidget) -> None:
        header = widget.findChild(QWidget, "institutionalHeader")
        if header is None:
            return
        header.setStyleSheet(
            "QFrame#institutionalHeader {background:#005EB8; border:none; "
            "border-bottom:3px solid #00A9E0;}"
            "QFrame#institutionalHeader QLabel {background:transparent; border:none; color:#FFFFFF;}"
            "QLabel#headerMode {background:#1675C5; border:1px solid #73B3DD; border-radius:10px; "
            "padding:4px 9px; color:#FFFFFF; font-size:9px; font-weight:700;}"
            "QLabel#headerStatus {background:#167A68; border:1px solid #40C1AC; border-radius:10px; "
            "padding:4px 9px; color:#FFFFFF; font-size:9px; font-weight:700;}"
            "QDateEdit {min-width:112px; padding:5px 8px; background:#FFFFFF; color:#00345F; "
            "border:1px solid #73B3DD; border-radius:5px;}"
        )

    def set_dark(self) -> None:
        self._theme = DarkTheme()

    def set_light(self) -> None:
        self._theme = LightTheme()

    def toggle(self) -> None:
        if isinstance(self._theme, DarkTheme):
            self.set_light()
        else:
            self.set_dark()
