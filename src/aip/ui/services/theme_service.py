from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.themes.dark_theme import DarkTheme
from aip.ui.themes.light_theme import LightTheme


class ThemeService:
    """Applies the active UI theme to widgets."""

    def __init__(self) -> None:
        self._theme = LightTheme()

    def apply(self, widget: QWidget) -> None:
        widget.setStyleSheet(self._theme.stylesheet())

    def set_dark(self) -> None:
        self._theme = DarkTheme()

    def set_light(self) -> None:
        self._theme = LightTheme()

    def toggle(self) -> None:
        if isinstance(self._theme, DarkTheme):
            self.set_light()
        else:
            self.set_dark()
