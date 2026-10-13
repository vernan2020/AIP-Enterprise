from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QToolTip

from aip.ui.modules.macro_intelligence.viewmodels.macro_intelligence_view_model import (
    MacroForecastLabViewModel,
)
from aip.ui.modules.macro_intelligence.views.macro_forecast_lab_panel import (
    MacroForecastLabPanel,
)


class _Presenter:
    def build_forecast_lab(
        self,
        indicator_code: str,
        *,
        force_refresh: bool = False,
    ) -> MacroForecastLabViewModel:
        del force_refresh
        return MacroForecastLabViewModel(
            indicator_code=indicator_code,
            indicator_label=indicator_code,
            status="AVAILABLE",
        )


def test_forecast_lab_exposes_governed_multimodel_controls(qt_app) -> None:
    panel = MacroForecastLabPanel(_Presenter())  # type: ignore[arg-type]

    assert panel._indicator_combo.count() == 24
    assert panel._indicator_combo.currentData() == "TPM"
    codes = {
        panel._indicator_combo.itemData(index) for index in range(panel._indicator_combo.count())
    }
    assert {"FX_BUY", "TRI_CRC_60M", "TRI_USD_60M"}.issubset(codes)
    assert panel._run_button.text() == "EJECUTAR MODELOS"
    assert panel._model_table.columnCount() == 11
    assert panel._forecast_table.columnCount() == 5
    assert panel._ensemble_table.columnCount() == 3


def test_forecast_lab_persistent_hover_details_do_not_require_os_tooltip(qt_app) -> None:
    panel = MacroForecastLabPanel(_Presenter())  # type: ignore[arg-type]
    try:
        assert panel._hover_readout.objectName() == "macroForecastHoverReadout"
        assert "Pase el cursor" in panel._hover_readout.text()
        panel._chart.hover_readout_changed.emit("TPM · 10/2026 · 3.25% · Banda 80%: 3.10% – 3.40%")
        assert "Banda 80%" in panel._hover_readout.text()
        panel._chart.set_view_model(MacroForecastLabViewModel())
        assert "Pase el cursor" in panel._hover_readout.text()
        panel._chart.hover_readout_changed.emit("")
        assert "Pase el cursor" in panel._hover_readout.text()
    finally:
        panel.close()
        qt_app.processEvents()


def test_forecast_lab_kpis_reflow_and_retain_institutional_contrast(qt_app) -> None:
    panel = MacroForecastLabPanel(_Presenter())  # type: ignore[arg-type]
    try:
        assert panel._kpi_columns_for_width(640) == 2
        assert panel._kpi_columns_for_width(900) == 3
        assert panel._kpi_columns_for_width(1300) == 6
        panel._arrange_kpis(640)
        assert panel._kpi_columns == 2
        assert panel._kpi_grid is not None
        assert panel._kpi_grid.itemAtPosition(2, 1).widget() is panel._kpi_cards[5]
        panel._arrange_kpis(900)
        assert panel._kpi_columns == 3
        assert panel._kpi_grid.itemAtPosition(1, 2).widget() is panel._kpi_cards[5]
        panel._arrange_kpis(1300)
        assert panel._kpi_columns == 6
        assert panel._kpi_grid.itemAtPosition(0, 5).widget() is panel._kpi_cards[5]
        assert "stop:0 #00477F" in panel._kpi_cards[0].styleSheet()
        assert panel._kpi_values["p12"].textInteractionFlags() & (
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        assert panel._kpi_values["p12"].accessibleName() == "Valor de Proyección 12M"
        assert panel._kpi_cards[0].minimumHeight() >= 100
    finally:
        panel.close()
        qt_app.processEvents()


def test_forecast_lab_chart_resets_stale_tooltip_and_reduces_axis_labels(
    qt_app, monkeypatch
) -> None:
    panel = MacroForecastLabPanel(_Presenter())  # type: ignore[arg-type]
    calls: list[bool] = []
    monkeypatch.setattr(QToolTip, "hideText", lambda: calls.append(True))
    try:
        chart = panel._chart
        assert chart._visible_label_indexes(12, 180) == (0, 11)
        assert chart._visible_label_indexes(12, 90) == (0,)
        assert chart._visible_label_indexes(0, 90) == ()
        chart._tooltip_regions = [(chart.rect(), "obsolete")]
        chart.set_view_model(MacroForecastLabViewModel())
        assert not chart._tooltip_regions
        assert calls == [True]
        chart.leaveEvent(QEvent(QEvent.Type.Leave))
        assert calls == [True, True]
    finally:
        panel.close()
        qt_app.processEvents()
