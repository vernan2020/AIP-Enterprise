from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QSplitter, QVBoxLayout, QWidget

from aip.ui.modules.executive.presenters.executive_presenter import ExecutivePresenter
from aip.ui.modules.executive.viewmodels.executive_view_model import ExecutiveViewModel
from aip.ui.modules.executive.views.executive_decisions_view import ExecutiveDecisionsView
from aip.ui.modules.executive.views.executive_liquidity_view import ExecutiveLiquidityView
from aip.ui.modules.executive.views.executive_market_view import ExecutiveMarketView
from aip.ui.modules.executive.views.executive_portfolio_view import ExecutivePortfolioView
from aip.ui.modules.executive.views.executive_summary_view import ExecutiveSummaryView
from aip.ui.modules.executive.views.executive_toolbar import ExecutiveToolbar
from aip.ui.modules.executive.views.executive_trends_view import ExecutiveTrendsView
from aip.ui.modules.executive.widgets.executive_alert_panel import ExecutiveAlertPanel
from aip.ui.modules.executive.widgets.executive_donut_chart import ExecutiveDonutChart
from aip.ui.modules.executive.widgets.executive_kpi_strip import ExecutiveKPIWidget
from aip.ui.modules.executive.widgets.executive_metric_card import ExecutiveMetricCard
from aip.ui.modules.executive.widgets.executive_status_card import ExecutiveStatusCard
from aip.ui.modules.executive.widgets.executive_summary_table import ExecutiveSummaryTable


class ExecutiveWorkspace(QWidget):
    def __init__(self, presenter: ExecutivePresenter | None = None) -> None:
        super().__init__()
        self._presenter = presenter or ExecutivePresenter()
        self._view_model = self._presenter.build_view_model()
        self._toolbar = ExecutiveToolbar()
        self._summary = ExecutiveSummaryView(self._view_model.summary)
        self._portfolio = ExecutivePortfolioView(self._view_model.portfolio)
        self._liquidity = ExecutiveLiquidityView(self._view_model.liquidity)
        self._market = ExecutiveMarketView(self._view_model.market)
        self._decisions = ExecutiveDecisionsView(self._view_model.recommendations)
        self._trends = ExecutiveTrendsView(self._view_model.trends)
        self._alerts = ExecutiveAlertPanel(self._view_model.alerts)
        self._status_card = ExecutiveStatusCard("Ready")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._toolbar)
        layout.addWidget(ExecutiveMetricCard("Overview", "Executive Cockpit"))
        layout.addWidget(ExecutiveKPIWidget(self._view_model.summary))
        layout.addWidget(self._summary)
        layout.addWidget(ExecutiveSummaryTable(self._view_model.summary))
        layout.addWidget(ExecutiveDonutChart("Allocation", "Diversified"))

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.addWidget(self._portfolio)
        content_splitter.addWidget(self._liquidity)
        layout.addWidget(content_splitter, 1)

        market_splitter = QSplitter(Qt.Orientation.Horizontal)
        market_splitter.addWidget(self._market)
        market_splitter.addWidget(self._decisions)
        layout.addWidget(market_splitter, 1)

        scroll = QScrollArea()
        scroll.setWidget(self._trends)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._alerts)
        layout.addWidget(self._status_card)

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self.bind_view_model(self._view_model)

    def bind_view_model(self, view_model: ExecutiveViewModel) -> None:
        self._view_model = view_model
        self._status_card.setText(view_model.status)
        self._status_card.setToolTip(view_model.error or "")

    def view_model(self) -> ExecutiveViewModel:
        return self._view_model
