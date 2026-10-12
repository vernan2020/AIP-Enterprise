from __future__ import annotations

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
        panel._chart.hover_readout_changed.emit("")
        assert "Pase el cursor" in panel._hover_readout.text()
    finally:
        panel.close()
        qt_app.processEvents()
