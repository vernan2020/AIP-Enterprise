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

    assert panel._indicator_combo.count() == 7
    assert panel._indicator_combo.currentData() == "TPM"
    assert panel._run_button.text() == "EJECUTAR MODELOS"
    assert panel._model_table.columnCount() == 11
    assert panel._forecast_table.columnCount() == 5
    assert panel._ensemble_table.columnCount() == 3
