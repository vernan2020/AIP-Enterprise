from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from aip.ui.modules.price_risk.models.price_risk_row import RiskChartPoint


class RiskBarChartWidget(QWidget):
    """Compact institutional horizontal bar chart for presentation values."""

    def __init__(
        self,
        *,
        value_formatter: Callable[[Decimal], str] | None = None,
        show_secondary: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._points: tuple[RiskChartPoint, ...] = ()
        self._formatter = value_formatter or (lambda value: f"{value:,.2f}")
        self._show_secondary = show_secondary
        self.setMinimumHeight(210)

    def set_data(self, points: tuple[RiskChartPoint, ...]) -> None:
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

        margin_left = 118
        margin_right = 94
        margin_top = 16
        margin_bottom = 14
        available_width = max(20.0, self.width() - margin_left - margin_right)
        available_height = max(20.0, self.height() - margin_top - margin_bottom)
        row_height = available_height / max(1, len(self._points))
        max_value = max((abs(float(point.value)) for point in self._points), default=0.0) or 1.0

        label_font = QFont(self.font())
        label_font.setPointSize(8)
        value_font = QFont(label_font)
        value_font.setBold(True)

        for index, point in enumerate(self._points):
            y = margin_top + index * row_height
            bar_height = max(7.0, min(18.0, row_height * 0.48))
            bar_y = y + (row_height - bar_height) / 2
            width = available_width * abs(float(point.value)) / max_value

            painter.setFont(label_font)
            painter.setPen(QColor("#243746"))
            label_rect = QRectF(6, y, margin_left - 14, row_height)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                point.label,
            )

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#DCE9F5"))
            painter.drawRoundedRect(
                QRectF(margin_left, bar_y, available_width, bar_height),
                4,
                4,
            )
            painter.setBrush(QColor("#1F5A8A"))
            painter.drawRoundedRect(
                QRectF(margin_left, bar_y, max(2.0, width), bar_height),
                4,
                4,
            )

            painter.setFont(value_font)
            painter.setPen(QColor("#17324D"))
            value_text = self._formatter(point.value)
            if self._show_secondary:
                value_text += f"  ·  {point.secondary_value:.1f}%"
            value_rect = QRectF(
                margin_left + available_width + 8,
                y,
                margin_right - 10,
                row_height,
            )
            painter.drawText(
                value_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                value_text,
            )


class ParetoChartWidget(QWidget):
    """Pareto view: contribution bars plus cumulative contribution line."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: tuple[RiskChartPoint, ...] = ()
        self.setMinimumHeight(210)

    def set_data(self, points: tuple[RiskChartPoint, ...]) -> None:
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

        left = 40.0
        right = 28.0
        top = 18.0
        bottom = 42.0
        chart_width = max(40.0, self.width() - left - right)
        chart_height = max(40.0, self.height() - top - bottom)
        count = len(self._points)
        slot = chart_width / max(1, count)
        max_bar = max((float(point.value) for point in self._points), default=0.0) or 1.0
        max_cumulative = max(
            100.0,
            max((float(point.secondary_value) for point in self._points), default=100.0),
        )

        painter.setPen(QPen(QColor("#D7E0E8"), 1))
        painter.drawLine(QPointF(left, top + chart_height), QPointF(left + chart_width, top + chart_height))

        line_points: list[QPointF] = []
        for index, point in enumerate(self._points):
            center_x = left + slot * index + slot / 2
            bar_width = min(28.0, slot * 0.55)
            height = chart_height * float(point.value) / max_bar
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2B6F9F"))
            painter.drawRoundedRect(
                QRectF(center_x - bar_width / 2, top + chart_height - height, bar_width, height),
                3,
                3,
            )

            painter.setPen(QColor("#415466"))
            font = QFont(self.font())
            font.setPointSize(7)
            painter.setFont(font)
            label_rect = QRectF(center_x - slot / 2, top + chart_height + 5, slot, bottom - 6)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                point.label[:12],
            )

            cumulative_y = top + chart_height * (1.0 - float(point.secondary_value) / max_cumulative)
            line_points.append(QPointF(center_x, cumulative_y))

        if len(line_points) >= 2:
            painter.setPen(QPen(QColor("#C9892B"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(QPolygonF(line_points))

        painter.setBrush(QColor("#C9892B"))
        painter.setPen(Qt.PenStyle.NoPen)
        for point in line_points:
            painter.drawEllipse(point, 3.5, 3.5)
