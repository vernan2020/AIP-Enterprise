from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class PortfolioHistoryLineChart(QWidget):
    """Compact institutional line chart for one historical portfolio KPI."""

    def __init__(
        self,
        *,
        value_formatter: Callable[[Decimal], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._points: tuple[tuple[date, Decimal | None], ...] = ()
        self._formatter = value_formatter or (lambda value: f"{value:,.2f}")
        self.setMinimumHeight(205)

    def set_data(self, points: tuple[tuple[date, Decimal | None], ...]) -> None:
        self._points = tuple(points)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        valid = [(cutoff, value) for cutoff, value in self._points if value is not None]
        if not valid:
            painter.setPen(QColor("#718096"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        left = 64.0
        right = 18.0
        top = 35.0
        bottom = 30.0
        plot_width = max(30.0, self.width() - left - right)
        plot_height = max(30.0, self.height() - top - bottom)

        values = [float(value) for _, value in valid if value is not None]
        minimum = min(values)
        maximum = max(values)
        spread = maximum - minimum
        padding = max(abs(maximum) * 0.04, spread * 0.12, 0.01)
        y_min = minimum - padding
        y_max = maximum + padding
        if y_max <= y_min:
            y_max = y_min + 1.0

        grid_pen = QPen(QColor("#E7EDF3"))
        grid_pen.setWidthF(1.0)
        label_font = QFont(self.font())
        label_font.setPointSize(8)
        painter.setFont(label_font)

        for index in range(4):
            ratio = index / 3
            y = top + plot_height * ratio
            axis_value = y_max - (y_max - y_min) * ratio
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(left, y), QPointF(left + plot_width, y))
            painter.setPen(QColor("#718096"))
            painter.drawText(
                QRectF(0, y - 9, left - 7, 18),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                self._axis_label(Decimal(str(axis_value))),
            )

        coordinates: list[QPointF] = []
        count = len(valid)
        for index, (_, point_value) in enumerate(valid):
            assert point_value is not None
            x_ratio = index / max(1, count - 1)
            y_ratio = (float(point_value) - y_min) / (y_max - y_min)
            x = left + plot_width * x_ratio
            y = top + plot_height * (1.0 - y_ratio)
            coordinates.append(QPointF(x, y))

        path = QPainterPath()
        path.moveTo(coordinates[0])
        for coordinate in coordinates[1:]:
            path.lineTo(coordinate)

        line_pen = QPen(QColor("#1F5A8A"))
        line_pen.setWidthF(2.2)
        painter.setPen(line_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1F5A8A"))
        marker_step = max(1, len(coordinates) // 18)
        for index, coordinate in enumerate(coordinates):
            if index % marker_step == 0 or index == len(coordinates) - 1:
                painter.drawEllipse(coordinate, 3.1, 3.1)

        first_date = valid[0][0]
        middle_date = valid[len(valid) // 2][0]
        last_date = valid[-1][0]
        painter.setPen(QColor("#718096"))
        painter.drawText(
            QRectF(left, top + plot_height + 7, plot_width / 3, 18),
            Qt.AlignmentFlag.AlignLeft,
            first_date.strftime("%b-%y"),
        )
        painter.drawText(
            QRectF(left + plot_width / 3, top + plot_height + 7, plot_width / 3, 18),
            Qt.AlignmentFlag.AlignCenter,
            middle_date.strftime("%b-%y"),
        )
        painter.drawText(
            QRectF(left + 2 * plot_width / 3, top + plot_height + 7, plot_width / 3, 18),
            Qt.AlignmentFlag.AlignRight,
            last_date.strftime("%b-%y"),
        )

        latest = valid[-1][1]
        assert latest is not None
        header_font = QFont(self.font())
        header_font.setPointSize(10)
        header_font.setBold(True)
        painter.setFont(header_font)
        painter.setPen(QColor("#17324D"))
        painter.drawText(
            QRectF(left, 5, plot_width, 22),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self._formatter(latest),
        )

        if len(valid) > 1:
            previous = valid[-2][1]
            assert previous is not None
            delta = latest - previous
            delta_font = QFont(self.font())
            delta_font.setPointSize(8)
            painter.setFont(delta_font)
            painter.setPen(QColor("#617386"))
            painter.drawText(
                QRectF(left, 7, plot_width * 0.65, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"Δ último corte {self._signed(delta)}",
            )

    def _axis_label(self, value: Decimal) -> str:
        formatted = self._formatter(value)
        return formatted.replace("₡", "").replace(" MM", "")

    def _signed(self, value: Decimal) -> str:
        prefix = "+" if value > 0 else ""
        return f"{prefix}{self._formatter(value)}"
