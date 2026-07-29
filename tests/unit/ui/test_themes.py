from __future__ import annotations

from aip.ui.themes.dark_theme import DarkTheme
from aip.ui.themes.light_theme import LightTheme
from aip.ui.themes.palette import ThemePalette


def test_theme_palette_exposes_expected_colors() -> None:
    palette = ThemePalette()
    assert palette.primary == "#2563eb"
    assert palette.surface == "#ffffff"


def test_themes_expose_stylesheets() -> None:
    dark = DarkTheme()
    light = LightTheme()

    assert dark.stylesheet()
    assert light.stylesheet()
