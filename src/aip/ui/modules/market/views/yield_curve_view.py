from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from aip.ui.modules.market.widgets.curve_chart import CurveChart


class YieldCurveView(QWidget):
    def __init__(self, curve_points: tuple[object, ...] | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._chart = CurveChart(curve_points or ())
        layout.addWidget(self._chart)
