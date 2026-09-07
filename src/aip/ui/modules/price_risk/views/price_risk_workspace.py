from __future__ import annotations

from aip.ui.modules.price_risk.presenters.price_risk_presenter import PriceRiskPresenter
from aip.ui.modules.price_risk.viewmodels.price_risk_view_model import PriceRiskViewModel
from aip.ui.modules.price_risk.views.portfolio_var_simulator_view import (
    PortfolioVaRSimulatorView,
)
from aip.ui.modules.price_risk.views.price_risk_view import PriceRiskView


class PriceRiskWorkspace(PriceRiskView):
    """Composite price-risk workspace including the isolated VeR simulator."""

    def __init__(self, presenter: PriceRiskPresenter) -> None:
        super().__init__(presenter)
        self.setObjectName("priceRiskCompositeWorkspace")
        self._simulator_page = PortfolioVaRSimulatorView(presenter)
        self._tabs.insertTab(1, self._simulator_page, "Simulador · VeR")
        self._simulator_page.bind_securities(self._view_model.simulation_securities)

    def _bind_view_model(self, vm: PriceRiskViewModel) -> None:
        super()._bind_view_model(vm)
        simulator = getattr(self, "_simulator_page", None)
        if simulator is not None:
            simulator.bind_securities(vm.simulation_securities)

    def refresh(self) -> None:
        simulator = getattr(self, "_simulator_page", None)
        if simulator is not None:
            simulator.clear_scenario(reset_result=True)
        super().refresh()

    def closeEvent(self, event) -> None:  # noqa: N802
        simulator = getattr(self, "_simulator_page", None)
        if simulator is not None:
            simulator.shutdown()
        super().closeEvent(event)
