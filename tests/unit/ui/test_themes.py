from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from aip.ui.services.theme_service import ThemeService
from aip.ui.themes.dark_theme import DarkTheme
from aip.ui.themes.light_theme import LightTheme
from aip.ui.themes.palette import ThemePalette


def test_theme_palette_exposes_coopealianza_brand_colors() -> None:
    palette = ThemePalette()
    assert palette.primary == "#005EB8"
    assert palette.secondary == "#00A9E0"
    assert palette.tertiary == "#40C1AC"
    assert palette.surface == "#FFFFFF"


def test_themes_expose_stylesheets() -> None:
    dark = DarkTheme()
    light = LightTheme()

    assert dark.stylesheet()
    assert light.stylesheet()


def test_theme_service_inserts_coopealianza_logo_once(qt_app) -> None:
    root = QWidget()
    root_layout = QVBoxLayout(root)
    header = QFrame(root)
    header.setObjectName("institutionalHeader")
    header.setLayout(QHBoxLayout())
    root_layout.addWidget(header)

    service = ThemeService()
    service.apply(root)
    service.apply(root)
    qt_app.processEvents()

    logos = header.findChildren(QLabel, "coopealianzaHeaderLogo")
    assert len(logos) == 1
    assert logos[0].pixmap() is not None
    assert not logos[0].pixmap().isNull()
    assert logos[0].width() == 236
    assert logos[0].height() == 48
