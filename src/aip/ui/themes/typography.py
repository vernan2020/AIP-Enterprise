"""Installed fonts for the real AIP desktop application (no font binaries)."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

UI_FONTS = ("Inter", "IBM Plex Sans", "Segoe UI", "Noto Sans", "Lucida Sans Unicode", "Arial")
NUMERIC_FONTS = (
    "IBM Plex Mono",
    "Cascadia Mono",
    "Consolas",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Courier New",
)


def choose_installed_font(
    available: Iterable[str], preferred: tuple[str, ...], fallback: str
) -> str:
    names = {name.casefold(): name for name in available}
    return next((names[name.casefold()] for name in preferred if name.casefold() in names), fallback)


def _resolve(preferred: tuple[str, ...]) -> str:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return "Sans Serif"
    return choose_installed_font(QFontDatabase.families(), preferred, app.font().family())


def interface_font_family() -> str:
    return _resolve(UI_FONTS)


def numeric_font_family() -> str:
    return _resolve(NUMERIC_FONTS)
