"""Image exports must preserve the actual Qt-rendered chart and user files."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QLabel, QWidget

from aip.ui.widgets.chart_png_export import export_widget_png


def test_chart_png_exports_real_qt_render_and_can_be_read(qt_app, tmp_path) -> None:
    chart = QLabel("VeR 95% · ₡299,78 MM")
    chart.resize(360, 140)
    chart.show()
    qt_app.processEvents()
    try:
        target = tmp_path / "riesgo-precio.png"
        width, height = export_widget_png(chart, target)
        assert width >= 360 and height >= 140
        assert target.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert QImageReader(str(target)).canRead()
        assert chart.text() == "VeR 95% · ₡299,78 MM"
    finally:
        chart.close()
        qt_app.processEvents()


def test_chart_png_rejects_zero_sized_widgets_without_partial_file(qt_app, tmp_path) -> None:
    chart = QWidget()
    chart.resize(0, 0)
    target = tmp_path / "invalid.png"
    with pytest.raises(ValueError, match="dimensiones"):
        export_widget_png(chart, target)
    assert not target.exists()
    chart.close()


def test_chart_png_failed_write_does_not_replace_user_data(qt_app, tmp_path) -> None:
    chart = QLabel("Proyección BCCR")
    chart.resize(240, 90)
    target = tmp_path / "missing-directory" / "plot.png"
    with pytest.raises(OSError):
        export_widget_png(chart, target)
    assert not target.exists()
    chart.close()
