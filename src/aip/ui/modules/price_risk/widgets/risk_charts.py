from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from aip.ui.modules.price_risk.models.price_risk_row import RiskChartPoint


class RiskBarChartWidget(QWidget):
    """Gráfico horizontal compacto para magnitudes de riesgo ya calculadas."""

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
            painter.setPen(QColor("#7B8D98"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        margin_left = 122
        margin_right = 112
        margin_top = 14
        margin_bottom = 12
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
            painter.setPen(QColor("#183247"))
            label_rect = QRectF(6, y, margin_left - 14, row_height)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                point.label,
            )

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#EAF4FA"))
            painter.drawRoundedRect(
                QRectF(margin_left, bar_y, available_width, bar_height),
                4,
                4,
            )
            if point.value < 0:
                fill = QColor("#E4002B")
            elif point.value > 0:
                fill = QColor("#005EB8")
            else:
                fill = QColor("#939598")
            painter.setBrush(fill)
            painter.drawRoundedRect(
                QRectF(margin_left, bar_y, max(2.0, width), bar_height),
                4,
                4,
            )

            painter.setFont(value_font)
            painter.setPen(QColor("#00345F"))
            value_text = self._formatter(point.value)
            if self._show_secondary:
                value_text += f" · {point.secondary_value:.1f}%"
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
    """Contribución individual y acumulada al escenario VeR seleccionado."""

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
            painter.setPen(QColor("#7B8D98"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        left = 42.0
        right = 30.0
        top = 18.0
        bottom = 38.0
        chart_width = max(40.0, self.width() - left - right)
        chart_height = max(40.0, self.height() - top - bottom)
        count = len(self._points)
        slot = chart_width / max(1, count)
        max_bar = max((abs(float(point.value)) for point in self._points), default=0.0) or 1.0
        cumulative_values = [float(point.secondary_value) for point in self._points]
        max_cumulative = max(100.0, max(cumulative_values, default=100.0))
        min_cumulative = min(0.0, min(cumulative_values, default=0.0))
        cumulative_span = max(max_cumulative - min_cumulative, 1.0)

        painter.setPen(QPen(QColor("#D5DEE3"), 1))
        painter.drawLine(
            QPointF(left, top + chart_height),
            QPointF(left + chart_width, top + chart_height),
        )

        hundred_y = top + chart_height * (1.0 - (100.0 - min_cumulative) / cumulative_span)
        painter.setPen(QPen(QColor("#40C1AC"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(left, hundred_y), QPointF(left + chart_width, hundred_y))

        line_points: list[QPointF] = []
        for index, point in enumerate(self._points):
            center_x = left + slot * index + slot / 2
            bar_width = max(1.5, min(18.0, slot * 0.62))
            height = chart_height * abs(float(point.value)) / max_bar * 0.50
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#005EB8") if point.value >= 0 else QColor("#E4002B"))
            painter.drawRoundedRect(
                QRectF(center_x - bar_width / 2, top + chart_height - height, bar_width, height),
                2,
                2,
            )

            cumulative_y = top + chart_height * (
                1.0 - (float(point.secondary_value) - min_cumulative) / cumulative_span
            )
            line_points.append(QPointF(center_x, cumulative_y))

        if len(line_points) >= 2:
            painter.setPen(QPen(QColor("#00A9E0"), 2.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(QPolygonF(line_points))

        painter.setBrush(QColor("#00A9E0"))
        painter.setPen(Qt.PenStyle.NoPen)
        for point in line_points:
            painter.drawEllipse(point, 2.5, 2.5)

        painter.setPen(QColor("#566D7C"))
        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(
            QRectF(left, 0, chart_width, 18),
            Qt.AlignmentFlag.AlignRight,
            "Línea celeste: contribución acumulada · referencia verde: 100%",
        )
