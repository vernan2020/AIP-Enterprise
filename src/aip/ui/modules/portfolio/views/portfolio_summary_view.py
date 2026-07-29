from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget

from aip.ui.modules.portfolio.widgets.portfolio_metric_card import PortfolioMetricCard


class PortfolioSummaryView(QWidget):
    def __init__(self, summary: object) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        for title, value in [
            ("Portfolio", getattr(summary, "portfolio_name", "")),
            ("Valuation Date", getattr(summary, "valuation_date", "")),
            ("Market Value", getattr(summary, "market_value", "")),
            ("Book Value", getattr(summary, "book_value", "")),
            ("Total Positions", str(getattr(summary, "total_positions", 0))),
            ("Weighted Yield", getattr(summary, "weighted_yield", "")),
            ("Modified Duration", getattr(summary, "modified_duration", "")),
            ("HQLA %", getattr(summary, "hqla_percent", "")),
            ("MIL Eligible %", getattr(summary, "mil_eligible_percent", "")),
        ]:
            layout.addWidget(PortfolioMetricCard(title, value))
