from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from aip.ui.modules.portfolio.models.portfolio_dashboard_point import PortfolioDashboardPoint


class PortfolioDashboardBarChart(QWidget):
    """Executive ranked bars with subtle grid, rank markers and value labels."""

    _TEXT = QColor("#17324D")
    _MUTED = QColor("#6F8090")
    _TRACK = QColor("#ECF2F6")
    _GRID = QColor("#E7EEF3")
    _ACCENT = QColor("#1F6F9F")

    def __init__(
        self,
        *,
        value_formatter: Callable[[Decimal], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._points: tuple[PortfolioDashboardPoint, ...] = ()
        self._formatter = value_formatter or (lambda value: f"{value:,.1f}%")
        self.setMinimumHeight(220)

    def set_data(self, points: tuple[PortfolioDashboardPoint, ...]) -> None:
        self._points = tuple(points)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        if not self._points:
            painter.setPen(self._MUTED)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        left, right, top, bottom = 132.0, 92.0, 14.0, 12.0
        width = max(40.0, self.width() - left - right)
        height = max(40.0, self.height() - top - bottom)
        row_height = height / max(1, len(self._points))
        maximum = max((abs(float(point.value)) for point in self._points), default=0.0) or 1.0

        for grid_fraction in (0.25, 0.50, 0.75, 1.0):
            x = left + width * grid_fraction
            painter.setPen(QPen(self._GRID, 1))
            painter.drawLine(QPointF(x, top), QPointF(x, top + height))

        label_font = QFont(self.font())
        label_font.setPointSize(8)
        value_font = QFont(label_font)
        value_font.setBold(True)

        for index, point in enumerate(self._points):
            y = top + row_height * index
            bar_height = max(8.0, min(18.0, row_height * 0.44))
            bar_y = y + (row_height - bar_height) / 2.0
            bar_width = width * abs(float(point.value)) / maximum

            painter.setFont(label_font)
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(22, y, left - 30, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                point.label[:20],
            )

            if index < 3:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#DDECF5"))
                painter.drawEllipse(QPointF(10.0, y + row_height / 2.0), 8.0, 8.0)
                painter.setFont(value_font)
                painter.setPen(QColor("#1B5E88"))
                painter.drawText(
                    QRectF(2, y, 16, row_height),
                    Qt.AlignmentFlag.AlignCenter,
                    str(index + 1),
                )

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._TRACK)
            painter.drawRoundedRect(QRectF(left, bar_y, width, bar_height), 6, 6)

            fill = self._ACCENT if index >= 3 else QColor("#145D8A")
            gradient = QLinearGradient(left, 0, left + max(2.0, bar_width), 0)
            gradient.setColorAt(0.0, fill)
            gradient.setColorAt(1.0, fill.lighter(125))
            painter.setBrush(gradient)
            painter.drawRoundedRect(
                QRectF(left, bar_y, max(2.0, bar_width), bar_height),
                6,
                6,
            )

            painter.setFont(value_font)
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(left + width + 6, y, right - 10, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                self._formatter(point.value),
            )
