"""Regressions for installed financial typography across themes and KPIs."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QTableWidget

from aip.ui.modules.macro_intelligence.views.macro_intelligence_workspace import (
    _MacroMetricCard,
)
from aip.ui.themes.dark_theme import DarkTheme
from aip.ui.themes.light_theme import LightTheme
from aip.ui.themes.typography import (
    NUMERIC_FONTS,
    UI_FONTS,
    apply_application_typography,
    choose_installed_font,
    interface_font_family,
    numeric_font_family,
)


def test_typography_selects_only_installed_fonts() -> None:
    installed = ("Consolas", "Segoe UI", "Lucida Sans Unicode")
    assert choose_installed_font(installed, UI_FONTS, "Fallback") == "Segoe UI"
    assert choose_installed_font(installed, NUMERIC_FONTS, "Fallback") == "Consolas"
    assert choose_installed_font((), UI_FONTS, "Fallback") == "Fallback"
    assert choose_installed_font(("inter",), UI_FONTS, "Fallback") == "inter"


def test_financial_font_tokens_apply_to_both_themes(qt_app: QApplication) -> None:
    for theme in (LightTheme(), DarkTheme()):
        qss = theme.stylesheet()
        assert f'font-family: "{interface_font_family()}";' in qss
        assert f'font-family: "{numeric_font_family()}";' in qss


def test_macro_kpi_uses_monospace_without_altering_financial_value(
    qt_app: QApplication,
) -> None:
    card = _MacroMetricCard("Tipo de cambio")
    try:
        card._value.setText("₡454.85")
        assert numeric_font_family() in card._value.styleSheet()
        assert card._value.text() == "₡454.85"
    finally:
        card.close()
        qt_app.processEvents()


def test_global_application_font_covers_windows_dialogs_and_late_widgets(
    qt_app: QApplication,
) -> None:
    original = qt_app.font()
    try:
        resolved = apply_application_typography(qt_app)
        assert resolved == interface_font_family()
        assert qt_app.font().family() == resolved
        dialog = QDialog()
        label = QLabel("Indicador regulatorio", dialog)
        table = QTableWidget(1, 2, dialog)
        try:
            assert dialog.font().family() == resolved
            assert label.font().family() == resolved
            assert table.font().family() == resolved
            assert apply_application_typography(qt_app) == resolved
        finally:
            dialog.close()
            qt_app.processEvents()
    finally:
        qt_app.setFont(original)
