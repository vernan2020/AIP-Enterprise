from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QSizePolicy, QWidget

from aip.ui.modules.market.widgets.market_metric_card import MarketMetricCard


class MarketSummaryView(QWidget):
    """Banda compacta de indicadores del diseño histórico de Mercado."""

    def __init__(self, summary: object) -> None:
        super().__init__()
        self.setObjectName("marketSummaryView")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._cards: dict[str, MarketMetricCard] = {}
        self._build_ui(summary)

    def _build_ui(self, summary: object) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(7)
        for column in range(4):
            layout.setColumnStretch(column, 1)

        cards = (
            ("market_date", "Fecha de Mercado", getattr(summary, "market_date", "")),
            ("curves_loaded", "Curvas Cargadas", str(getattr(summary, "curves_loaded", 0))),
            ("pricing_date", "Fecha de Valoración", getattr(summary, "pricing_date", "")),
            (
                "relative_value_opportunities",
                "Oportunidades RV",
                str(getattr(summary, "relative_value_opportunities", 0)),
            ),
            ("average_yield", "TIR Promedio", getattr(summary, "average_yield", "")),
            (
                "average_duration",
                "Duración Promedio",
                getattr(summary, "average_duration", ""),
            ),
            (
                "average_spread",
                "Diferencial Promedio",
                getattr(summary, "average_spread", ""),
            ),
            ("market_status", "Estado de Mercado", getattr(summary, "market_status", "")),
        )
        for index, (key, title, value) in enumerate(cards):
            card = MarketMetricCard(
                title,
                str(value),
                status=self._status_from_value(value),
            )
            self._cards[key] = card
            layout.addWidget(card, index // 4, index % 4)

    def bind_summary(self, summary: object) -> None:
        values = {
            "market_date": getattr(summary, "market_date", ""),
            "curves_loaded": str(getattr(summary, "curves_loaded", 0)),
            "pricing_date": getattr(summary, "pricing_date", ""),
            "relative_value_opportunities": str(
                getattr(summary, "relative_value_opportunities", 0)
            ),
            "average_yield": getattr(summary, "average_yield", ""),
            "average_duration": getattr(summary, "average_duration", ""),
            "average_spread": getattr(summary, "average_spread", ""),
            "market_status": getattr(summary, "market_status", ""),
        }
        for key, value in values.items():
            card = self._cards.get(key)
            if card is not None:
                card.set_value(str(value))

    @staticmethod
    def _status_from_value(value: object) -> str:
        normalized = str(value).strip().casefold()
        if normalized in {"", "n/a", "na", "none", "no disponible", "n/d"}:
            return "neutral"
        return "configurado"
