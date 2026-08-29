from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class CurveChart(QWidget):
    """Minimal curve chart view for the market workspace."""

    def __init__(
        self, curve_points: tuple[object, ...] | None = None, title: str = "Yield Curve"
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Point", "Tenor", "Value"])
        layout.addWidget(self._table)
        self.bind_curve_points(curve_points or ())

    def bind_curve_points(self, curve_points: tuple[object, ...]) -> None:
        self._table.setRowCount(len(curve_points))
        for row_index, point in enumerate(curve_points):
            values = [
                getattr(point, "label", ""),
                getattr(point, "tenor", ""),
                getattr(point, "value", ""),
            ]
            for column_index, value in enumerate(values):
                self._table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
