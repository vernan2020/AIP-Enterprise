from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.macro_intelligence.views.macro_forecast_lab_panel import (
    MacroForecastLabPanel,
)
from aip.ui.modules.macro_intelligence.views.macro_intelligence_workspace import (
    MacroIntelligenceWorkspace,
)


class MacroIntelligenceView(MacroIntelligenceWorkspace):
    """Macro workspace extended with the governed multimodel Forecast Lab."""

    def __init__(
        self,
        *,
        application_factory: DemoApplicationFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(application_factory=application_factory, parent=parent)
        self._forecast_lab = MacroForecastLabPanel(self._presenter)
        self._forecast_lab_index = self._tabs.insertTab(
            1,
            self._forecast_lab,
            "Forecast Lab · Modelos",
        )
        self._tabs.currentChanged.connect(self._forecast_tab_changed)

    def _forecast_tab_changed(self, index: int) -> None:
        if index == self._forecast_lab_index:
            self._forecast_lab.ensure_loaded()


__all__ = ["MacroIntelligenceView", "MacroIntelligenceWorkspace"]
