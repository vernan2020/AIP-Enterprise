from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from aip.ui.modules.executive.widgets.executive_trend_chart import ExecutiveTrendChart


class ExecutiveTrendsView(QWidget):
    def __init__(self, trends: tuple[tuple[str, tuple[str, ...]], ...]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        for label, points in trends:
            layout.addWidget(ExecutiveTrendChart(label, points))
