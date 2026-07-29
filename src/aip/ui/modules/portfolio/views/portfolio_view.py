from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel
from aip.ui.modules.portfolio.views.portfolio_details_view import PortfolioDetailsView
from aip.ui.modules.portfolio.views.portfolio_positions_view import PortfolioPositionsView
from aip.ui.modules.portfolio.views.portfolio_summary_view import PortfolioSummaryView
from aip.ui.modules.portfolio.views.portfolio_toolbar import PortfolioToolbar
from aip.ui.modules.portfolio.widgets.portfolio_filter_panel import PortfolioFilterPanel
from aip.ui.modules.portfolio.widgets.portfolio_status_badge import PortfolioStatusBadge


class PortfolioView(QWidget):
    def __init__(self, presenter: PortfolioPresenter | None = None) -> None:
        super().__init__()
        self._presenter = presenter or PortfolioPresenter()
        self._view_model = self._presenter.build_view_model()
        self._toolbar = PortfolioToolbar()
        self._summary = PortfolioSummaryView(self._view_model.summary)
        self._filter_panel = PortfolioFilterPanel()
        self._positions = PortfolioPositionsView(self._view_model.rows)
        self._details = PortfolioDetailsView(self._view_model.rows[0] if self._view_model.rows else None)
        self._status_bar = PortfolioStatusBadge("Portfolio ready")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._summary)
        layout.addWidget(self._filter_panel)

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.addWidget(self._positions)
        content_splitter.addWidget(self._details)
        layout.addWidget(content_splitter, 1)
        layout.addWidget(self._status_bar)

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self.bind_view_model(self._view_model)

    def bind_view_model(self, view_model: PortfolioViewModel) -> None:
        self._view_model = view_model
        self._summary = PortfolioSummaryView(view_model.summary)
        self._positions = PortfolioPositionsView(view_model.rows)
        self._details = PortfolioDetailsView(view_model.rows[0] if view_model.rows else None)
        self._status_bar.setText(view_model.status)
        self._status_bar.setToolTip(view_model.error or "")

    def view_model(self) -> PortfolioViewModel:
        return self._view_model

    def selected_row(self) -> object | None:
        return self._view_model.rows[0] if self._view_model.rows else None
