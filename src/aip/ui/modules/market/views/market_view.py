from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from aip.ui.modules.market.presenters.market_presenter import MarketPresenter
from aip.ui.modules.market.viewmodels.market_view_model import MarketViewModel
from aip.ui.modules.market.views.market_summary_view import MarketSummaryView
from aip.ui.modules.market.views.pricing_view import PricingView
from aip.ui.modules.market.views.relative_value_view import RelativeValueView
from aip.ui.modules.market.views.yield_curve_view import YieldCurveView
from aip.ui.modules.market.widgets.market_filter_panel import MarketFilterPanel
from aip.ui.modules.market.widgets.market_metric_card import MarketMetricCard
from aip.ui.modules.market.widgets.market_status_badge import MarketStatusBadge


class MarketView(QWidget):
    def __init__(self, presenter: MarketPresenter | None = None) -> None:
        super().__init__()
        self._presenter = presenter or MarketPresenter()
        self._view_model = self._presenter.build_view_model()
        self._status_badge = MarketStatusBadge("Ready")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(MarketSummaryView(self._view_model.summary))
        layout.addWidget(MarketFilterPanel())

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.addWidget(YieldCurveView(self._view_model.curve_points))
        content_splitter.addWidget(RelativeValueView(self._view_model.rows))
        layout.addWidget(content_splitter, 1)

        pricing_view = PricingView(self._view_model.rows)
        layout.addWidget(pricing_view)
        layout.addWidget(self._status_badge)

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self.bind_view_model(self._view_model)

    def bind_view_model(self, view_model: MarketViewModel) -> None:
        self._view_model = view_model
        self._status_badge.setText(view_model.status)
        self._status_badge.setToolTip(view_model.error or "")

    def view_model(self) -> MarketViewModel:
        return self._view_model
