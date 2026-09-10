from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PySide6.QtWidgets import QVBoxLayout, QWidget

from aip.ui.modules.rate_risk.controllers import RateRiskWorkspaceController
from aip.ui.modules.rate_risk.views.rate_risk_view import RateRiskView


class RateRiskWorkspace(QWidget):
    """UI coordinator for the passive RTILB view and application controller.

    Refreshing this widget reloads the immutable read-model for the active global
    cutoff. When the configured runtime is absent, the view remains explicitly in
    its UNCONFIGURED state and no financial values are synthesized.
    """

    def __init__(
        self,
        *,
        valuation_date_provider: Callable[[], date],
        controller: RateRiskWorkspaceController | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("rateRiskWorkspaceHost")
        self._valuation_date_provider = valuation_date_provider
        self._controller = controller
        self._view = RateRiskView()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view)

        self.refresh()

    @property
    def view(self) -> RateRiskView:
        return self._view

    @property
    def is_configured(self) -> bool:
        return self._controller is not None

    def refresh(self) -> None:
        controller = self._controller
        if controller is None:
            self._view.set_read_model(None)
            return

        cutoff_date = self._valuation_date_provider()
        self._view.set_read_model(controller.load(cutoff_date=cutoff_date))
