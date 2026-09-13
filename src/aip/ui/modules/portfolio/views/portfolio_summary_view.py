from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget

from aip.ui.modules.portfolio.widgets.portfolio_metric_card import PortfolioMetricCard


class PortfolioSummaryView(QWidget):
    def __init__(self, summary: object) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        for title, value in [
            ("Portafolio", getattr(summary, "portfolio_name", "")),
            ("Fecha de Valoración", getattr(summary, "valuation_date", "")),
            ("Valor de Mercado", getattr(summary, "market_value", "")),
            ("Valor en Libros", getattr(summary, "book_value", "")),
            ("Posiciones Totales", str(getattr(summary, "total_positions", 0))),
            ("TIR Ponderada", getattr(summary, "weighted_yield", "")),
            ("Duración Modificada", getattr(summary, "modified_duration", "")),
            ("HQLA %", getattr(summary, "hqla_percent", "")),
            ("MIL Elegible %", getattr(summary, "mil_eligible_percent", "")),
        ]:
            layout.addWidget(PortfolioMetricCard(title, value))
