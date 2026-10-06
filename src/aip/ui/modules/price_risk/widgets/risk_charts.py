from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from aip.ui.modules.price_risk.models.price_risk_row import RiskChartPoint


class RiskBarChartWidget(QWidget):
    """Professional horizontal risk bars with automatic zero-centred mode."""

    _TEXT = QColor("#17324D")
    _MUTED = QColor("#718096")
    _TRACK = QColor("#EEF3F7")
    _GRID = QColor("#DCE6EE")
    _POSITIVE = QColor("#126FA4")
    _NEGATIVE = QColor("#C53B32")
    _NEUTRAL = QColor("#8A98A6")

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
            self._draw_empty_state(painter)
            return

        left = 126.0
        right = 116.0
        top = 12.0
        bottom = 12.0
        width = max(50.0, self.width() - left - right)
        height = max(40.0, self.height() - top - bottom)
        row_height = height / max(1, len(self._points))

        values = tuple(float(point.value) for point in self._points)
        has_positive = any(value > 0 for value in values)
        has_negative = any(value < 0 for value in values)
        diverging = has_positive and has_negative

        label_font = QFont(self.font())
        label_font.setPointSize(8)
        value_font = QFont(label_font)
        value_font.setBold(True)

        if diverging:
            maximum = max((abs(value) for value in values), default=1.0) or 1.0
            center = left + width / 2.0
            half = width / 2.0
            painter.setPen(QPen(self._GRID, 1))
            painter.drawLine(QPointF(center, top), QPointF(center, top + height))
        else:
            maximum = max((abs(value) for value in values), default=1.0) or 1.0
            center = left
            half = width

        for index, point in enumerate(self._points):
            y = top + index * row_height
            bar_height = max(8.0, min(18.0, row_height * 0.48))
            bar_y = y + (row_height - bar_height) / 2.0
            numeric = float(point.value)
            bar_width = half * abs(numeric) / maximum

            painter.setFont(label_font)
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(6, y, left - 16, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                point.label[:24],
            )

            if not diverging:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self._TRACK)
                painter.drawRoundedRect(QRectF(left, bar_y, width, bar_height), 5, 5)

            fill = (
                self._POSITIVE if numeric > 0 else self._NEGATIVE if numeric < 0 else self._NEUTRAL
            )
            gradient = QLinearGradient(0, bar_y, 0, bar_y + bar_height)
            gradient.setColorAt(0.0, fill.lighter(112))
            gradient.setColorAt(1.0, fill)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)

            if diverging and numeric < 0:
                rect = QRectF(center - bar_width, bar_y, max(2.0, bar_width), bar_height)
            else:
                rect = QRectF(center, bar_y, max(2.0, bar_width), bar_height)
            painter.drawRoundedRect(rect, 5, 5)

            painter.setFont(value_font)
            painter.setPen(fill.darker(118) if numeric else self._TEXT)
            text = self._formatter(point.value)
            if self._show_secondary:
                text += f" · {point.secondary_value:.1f}%"
            painter.drawText(
                QRectF(left + width + 6, y, right - 10, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                text,
            )

    def _draw_empty_state(self, painter: QPainter) -> None:
        center = self.rect().center()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#F3F7FA"))
        painter.drawEllipse(QPointF(center.x(), center.y() - 10), 17, 17)
        painter.setPen(self._MUTED)
        font = QFont(self.font())
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, center.y() + 15, self.width(), 28),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Sin datos disponibles",
        )


class ParetoChartWidget(QWidget):
    """Pareto moderno: barras de contribución + línea acumulada y referencia 100%."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: tuple[RiskChartPoint, ...] = ()
        self.setMinimumHeight(230)

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

        left, right, top, bottom = 42.0, 28.0, 26.0, 42.0
        width = max(50.0, self.width() - left - right)
        height = max(50.0, self.height() - top - bottom)
        count = len(self._points)
        slot = width / max(1, count)
        max_bar = max((abs(float(point.value)) for point in self._points), default=0.0) or 1.0

        cumulative_values = [float(point.secondary_value) for point in self._points]
        max_cumulative = max(100.0, max(cumulative_values, default=100.0))
        min_cumulative = min(0.0, min(cumulative_values, default=0.0))
        cumulative_span = max(max_cumulative - min_cumulative, 1.0)

        for grid_index in range(5):
            y = top + height * grid_index / 4
            painter.setPen(QPen(QColor("#EEF2F5"), 1))
            painter.drawLine(QPointF(left, y), QPointF(left + width, y))

        hundred_y = top + height * (1.0 - (100.0 - min_cumulative) / cumulative_span)
        painter.setPen(QPen(QColor("#43A68A"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(left, hundred_y), QPointF(left + width, hundred_y))

        line_points: list[QPointF] = []
        for index, point in enumerate(self._points):
            center_x = left + slot * index + slot / 2
            bar_width = max(3.0, min(22.0, slot * 0.58))
            bar_height = height * abs(float(point.value)) / max_bar * 0.58
            fill = QColor("#126FA4") if point.value >= 0 else QColor("#C53B32")
            gradient = QLinearGradient(0, top + height - bar_height, 0, top + height)
            gradient.setColorAt(0.0, fill.lighter(118))
            gradient.setColorAt(1.0, fill)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(
                QRectF(center_x - bar_width / 2, top + height - bar_height, bar_width, bar_height),
                4,
                4,
            )

            cumulative_y = top + height * (
                1.0 - (float(point.secondary_value) - min_cumulative) / cumulative_span
            )
            line_points.append(QPointF(center_x, cumulative_y))

        if line_points:
            area = [QPointF(line_points[0].x(), top + height), *line_points]
            area.append(QPointF(line_points[-1].x(), top + height))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(30, 145, 194, 24))
            painter.drawPolygon(QPolygonF(area))

        if len(line_points) >= 2:
            painter.setPen(QPen(QColor("#1E91C2"), 2.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(QPolygonF(line_points))

        painter.setBrush(QColor("#1E91C2"))
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        for point in line_points:
            painter.drawEllipse(point, 3.2, 3.2)

        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor("#607486"))
        painter.drawText(
            QRectF(left, 0, width, 20),
            Qt.AlignmentFlag.AlignRight,
            "Barras: contribución · Línea: acumulado · Referencia: 100%",
        )

        label_indexes = sorted({0, count - 1, count // 3, (count * 2) // 3})
        painter.setPen(QColor("#718096"))
        for index in label_indexes:
            if not 0 <= index < count:
                continue
            center_x = left + slot * index + slot / 2
            painter.drawText(
                QRectF(center_x - 45, top + height + 7, 90, 22),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                self._points[index].label[:12],
            )
