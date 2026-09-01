from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from aip.ui.modules.liquidity.presenters.liquidity_presenter import LiquidityPresenter
from aip.ui.modules.liquidity.viewmodels.liquidity_view_model import LiquidityViewModel
from aip.ui.modules.liquidity.views.cashflow_view import CashflowView
from aip.ui.modules.liquidity.views.gap_view import GapView
from aip.ui.modules.liquidity.views.hqla_view import HQLAView
from aip.ui.modules.liquidity.views.liquidity_toolbar import LiquidityToolbar
from aip.ui.modules.liquidity.views.mil_view import MILView
from aip.ui.modules.liquidity.views.stress_view import StressView
from aip.ui.modules.liquidity.widgets.liquidity_filter_panel import LiquidityFilterPanel
from aip.ui.modules.liquidity.widgets.liquidity_metric_card import LiquidityMetricCard
from aip.ui.modules.liquidity.widgets.liquidity_status_badge import LiquidityStatusBadge


class LiquidityView(QWidget):
    def __init__(self, presenter: LiquidityPresenter | None = None) -> None:
        super().__init__()
        self._presenter = presenter or LiquidityPresenter()
        self._view_model = self._presenter.build_view_model()
        self._toolbar = LiquidityToolbar()
        self._status_badge = LiquidityStatusBadge("Ready")
        self._summary_cards: list[LiquidityMetricCard] = []
        self._cashflow_view: CashflowView | None = None
        self._gap_view: GapView | None = None
        self._hqla_view: HQLAView | None = None
        self._mil_view: MILView | None = None
        self._stress_view: StressView | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._toolbar)

        summary_layout = QVBoxLayout()
        self._summary_cards = [
            LiquidityMetricCard("Liquidity Date", self._view_model.summary.liquidity_date),
            LiquidityMetricCard("Cash Position", self._view_model.summary.cash_position),
            LiquidityMetricCard("Net Cash Flow", self._view_model.summary.net_cash_flow),
            LiquidityMetricCard("Liquidity Gap", self._view_model.summary.liquidity_gap),
            LiquidityMetricCard("HQLA Capacity", self._view_model.summary.hqla_capacity),
            LiquidityMetricCard(
                "MIL Eligible Capacity", self._view_model.summary.mil_eligible_capacity
            ),
            LiquidityMetricCard("Stress Result", self._view_model.summary.stress_result),
            LiquidityMetricCard("Policy Status", self._view_model.summary.policy_status),
        ]
        for card in self._summary_cards:
            summary_layout.addWidget(card)
        layout.addLayout(summary_layout)

        layout.addWidget(LiquidityFilterPanel())

        detail_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._cashflow_view = CashflowView(self._view_model.cashflow_rows)
        self._gap_view = GapView(self._view_model.gap_rows)
        detail_splitter.addWidget(self._cashflow_view)
        detail_splitter.addWidget(self._gap_view)
        layout.addWidget(detail_splitter, 1)

        detail_splitter2 = QSplitter(Qt.Orientation.Horizontal)
        self._hqla_view = HQLAView(self._view_model.hqla_rows)
        self._mil_view = MILView(self._view_model.mil_rows)
        detail_splitter2.addWidget(self._hqla_view)
        detail_splitter2.addWidget(self._mil_view)
        layout.addWidget(detail_splitter2, 1)

        self._stress_view = StressView(self._view_model.stress_rows)
        layout.addWidget(self._stress_view)
        layout.addWidget(self._status_badge)

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self.bind_view_model(self._view_model)

    def bind_view_model(self, view_model: LiquidityViewModel) -> None:
        self._view_model = view_model
        self._status_badge.setText(view_model.status)
        self._status_badge.setToolTip(view_model.error or "")
        if self._cashflow_view is not None:
            self._cashflow_view = CashflowView(view_model.cashflow_rows)
        if self._gap_view is not None:
            self._gap_view = GapView(view_model.gap_rows)
        if self._hqla_view is not None:
            self._hqla_view = HQLAView(view_model.hqla_rows)
        if self._mil_view is not None:
            self._mil_view = MILView(view_model.mil_rows)
        if self._stress_view is not None:
            self._stress_view = StressView(view_model.stress_rows)
        if self._summary_cards:
            self._summary_cards[0].setText(view_model.summary.liquidity_date)
            self._summary_cards[1].setText(view_model.summary.cash_position)
            self._summary_cards[2].setText(view_model.summary.net_cash_flow)
            self._summary_cards[3].setText(view_model.summary.liquidity_gap)
            self._summary_cards[4].setText(view_model.summary.hqla_capacity)
            self._summary_cards[5].setText(view_model.summary.mil_eligible_capacity)
            self._summary_cards[6].setText(view_model.summary.stress_result)
            self._summary_cards[7].setText(view_model.summary.policy_status)

    def view_model(self) -> LiquidityViewModel:
        return self._view_model
