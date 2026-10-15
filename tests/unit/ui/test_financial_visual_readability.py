"""AIP PRO-MAX hover and KPI typography must remain readable and traceable."""

from __future__ import annotations

from PySide6.QtCore import Qt

from aip.ui.modules.macro_intelligence.views.macro_intelligence_workspace import (
    _MacroMetricCard,
)
from aip.ui.themes.dark_theme import DarkTheme
from aip.ui.themes.light_theme import LightTheme
from aip.ui.widgets.chart_tooltip import build_chart_tooltip


def test_chart_tooltips_have_legible_type_and_escape_source_text() -> None:
    html = build_chart_tooltip(
        "ΔEVE <200 pb",
        (("Entidad", "Gobierno & BCCR"), ("Valor", "₡123.50")),
        note="Sensibilidad de tasas",
    )
    assert "font-size:14px" in html
    assert "font-size:13px" in html
    assert "font-size:12px" in html
    assert "bgcolor='#102D47'" in html
    assert "ΔEVE &lt;200 pb" in html
    assert "Gobierno &amp; BCCR" in html
    assert "₡123.50" in html


def test_tooltips_readable_in_both_institutional_themes(qt_app) -> None:
    for theme in (LightTheme(), DarkTheme()):
        qss = theme.stylesheet()
        tooltip = qss.split("QToolTip {", 1)[1].split("}", 1)[0]
        assert "font-size: 10pt;" in tooltip
        assert "padding: 8px 11px;" in tooltip


def test_macro_financial_kpi_is_legible_and_selectable(qt_app) -> None:
    card = _MacroMetricCard("Tipo de cambio")
    try:
        assert card.minimumHeight() >= 104
        assert card.accessibleName() == "Tipo de cambio"
        assert card._value.accessibleName() == "Valor de Tipo de cambio"
        assert card._value.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
        card._value.setText("₡454,85")
        assert card._value.text() == "₡454,85"
    finally:
        card.close()
        qt_app.processEvents()
