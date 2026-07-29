from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget

from aip.ui.modules.portfolio.widgets.portfolio_metric_card import PortfolioMetricCard


class MarketSummaryView(QWidget):
    def __init__(self, summary: object) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        for title, value in [
            ("Market Date", getattr(summary, "market_date", "")),
            ("Curves Loaded", str(getattr(summary, "curves_loaded", 0))),
            ("Pricing Date", getattr(summary, "pricing_date", "")),
            ("Relative Value Opportunities", str(getattr(summary, "relative_value_opportunities", 0))),
            ("Average Yield", getattr(summary, "average_yield", "")),
            ("Average Duration", getattr(summary, "average_duration", "")),
            ("Average Spread", getattr(summary, "average_spread", "")),
            ("Market Status", getattr(summary, "market_status", "")),
        ]:
            layout.addWidget(PortfolioMetricCard(title, value))
