from __future__ import annotations

from PySide6.QtCore import QPointF

from aip.ui.widgets.chart_tooltip import build_chart_tooltip, point_hit_rect


def test_chart_tooltip_omits_missing_values_but_keeps_zero() -> None:
    tooltip = build_chart_tooltip(
        "DV01 <CRC>",
        (
            ("Valor", "0"),
            ("No disponible", "N/D"),
            ("Vacío", ""),
            ("Spread", "+42 pb"),
        ),
        note="Contexto > dato",
    )

    assert "DV01 &lt;CRC&gt;" in tooltip
    assert ">0<" in tooltip
    assert "+42 pb" in tooltip
    assert "No disponible" not in tooltip
    assert "Vacío" not in tooltip
    assert "Contexto &gt; dato" in tooltip


def test_point_hit_rect_centers_on_chart_point() -> None:
    rect = point_hit_rect(QPointF(100.0, 50.0), radius=8.0)

    assert rect.left() == 92.0
    assert rect.top() == 42.0
    assert rect.right() == 108.0
    assert rect.bottom() == 58.0
    assert rect.contains(QPointF(100.0, 50.0))


def test_chart_tooltip_uses_high_contrast_dark_theme_markup() -> None:
    tooltip = build_chart_tooltip(
        "Curva BCCR",
        (("Plazo", "2.40 años"), ("Rendimiento", "5.286%")),
        note="Observación de mercado.",
    )

    assert "color:#FFFFFF" in tooltip
    assert "color:#C6E5F4" in tooltip
    assert "color:#A9D8EC" in tooltip
    assert "min-width:220px" in tooltip
