from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from aip.ui.modules.portfolio.models.portfolio_dashboard_point import PortfolioDashboardPoint


class PortfolioDashboardBarChart(QWidget):
    """Compact horizontal bar chart for portfolio dashboard presentation values."""

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
            painter.setPen(QColor("#718096"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        left = 118.0
        right = 88.0
        top = 14.0
        bottom = 12.0
        width = max(30.0, self.width() - left - right)
        height = max(30.0, self.height() - top - bottom)
        row_height = height / max(1, len(self._points))
        maximum = max((abs(float(point.value)) for point in self._points), default=0.0) or 1.0

        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)
        for index, point in enumerate(self._points):
            y = top + row_height * index
            bar_height = max(7.0, min(18.0, row_height * 0.48))
            bar_y = y + (row_height - bar_height) / 2
            bar_width = width * abs(float(point.value)) / maximum

            painter.setPen(QColor("#243746"))
            painter.drawText(
                QRectF(5, y, left - 12, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                point.label[:18],
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#DCE9F5"))
            painter.drawRoundedRect(QRectF(left, bar_y, width, bar_height), 4, 4)
            painter.setBrush(QColor("#1F5A8A"))
            painter.drawRoundedRect(
                QRectF(left, bar_y, max(2.0, bar_width), bar_height),
                4,
                4,
            )
            painter.setPen(QColor("#17324D"))
            painter.drawText(
                QRectF(left + width + 6, y, right - 10, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                self._formatter(point.value),
            )
