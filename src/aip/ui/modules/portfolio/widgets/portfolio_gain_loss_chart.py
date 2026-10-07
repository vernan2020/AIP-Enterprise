from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationChartPoint,
)
from aip.ui.widgets.chart_tooltip import build_chart_tooltip, show_chart_tooltip


class PortfolioGainLossBarChart(QWidget):
    """Native compact chart for authoritative accumulated valuation presentation."""

    _GAIN = QColor("#16794B")
    _LOSS = QColor("#B42318")
    _TRACK = QColor("#E9EEF3")
    _TEXT = QColor("#22384C")
    _MUTED = QColor("#718096")
    _AXIS = QColor("#CBD5DF")

    def __init__(
        self,
        *,
        mode: str = "value",
        value_formatter: Callable[[Decimal], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._points: tuple[PortfolioValuationChartPoint, ...] = ()
        self._mode = mode
        self._formatter = value_formatter or (lambda value: f"{value:+,.2f}")
        self._tooltip_regions: list[tuple[QRectF, str]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(180)

    def set_data(self, points: tuple[PortfolioValuationChartPoint, ...]) -> None:
        self._points = tuple(points)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        self._tooltip_regions = []

        if not self._points:
            painter.setPen(self._MUTED)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        if self._mode == "diverging":
            self._paint_diverging(painter)
        else:
            self._paint_values(painter)

    def _font(self, *, bold: bool = False) -> QFont:
        font = QFont(self.font())
        font.setPointSize(8)
        font.setBold(bold)
        return font

    def _paint_values(self, painter: QPainter) -> None:
        left, right, top, bottom = 132.0, 108.0, 10.0, 10.0
        width = max(30.0, self.width() - left - right)
        height = max(30.0, self.height() - top - bottom)
        row_height = height / max(1, len(self._points))
        maximum = max((abs(float(point.value)) for point in self._points), default=0.0) or 1.0

        for index, point in enumerate(self._points):
            y = top + row_height * index
            bar_height = max(7.0, min(18.0, row_height * 0.46))
            bar_y = y + (row_height - bar_height) / 2
            bar_width = width * abs(float(point.value)) / maximum

            painter.setFont(self._font())
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(6, y, left - 14, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                point.label[:22],
            )

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._TRACK)
            painter.drawRoundedRect(QRectF(left, bar_y, width, bar_height), 6, 6)
            fill = self._GAIN if point.value >= 0 else self._LOSS
            gradient = QLinearGradient(left, 0, left + max(2.0, bar_width), 0)
            gradient.setColorAt(0.0, fill)
            gradient.setColorAt(1.0, fill.lighter(122))
            painter.setBrush(gradient)
            painter.drawRoundedRect(
                QRectF(left, bar_y, max(2.0, bar_width), bar_height),
                6,
                6,
            )

            tooltip = build_chart_tooltip(
                point.label,
                (
                    ("Ganancia / pérdida", self._formatter(point.value)),
                    ("Resultado", "Ganancia" if point.value >= 0 else "Pérdida"),
                ),
                note="Resultado acumulado presentado por el motor de valorización.",
            )
            self._tooltip_regions.append(
                (QRectF(0, y, self.width(), row_height), tooltip)
            )
            painter.setFont(self._font(bold=True))
            painter.setPen(self._GAIN if point.value >= 0 else self._LOSS)
            painter.drawText(
                QRectF(left + width + 6, y, right - 10, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                self._formatter(point.value),
            )

    def _paint_diverging(self, painter: QPainter) -> None:
        left, right, top, bottom = 118.0, 96.0, 10.0, 10.0
        width = max(60.0, self.width() - left - right)
        half = width / 2.0
        center = left + half
        height = max(30.0, self.height() - top - bottom)
        row_height = height / max(1, len(self._points))
        maximum = (
            max(
                (
                    max(abs(float(point.positive)), abs(float(point.negative)))
                    for point in self._points
                ),
                default=0.0,
            )
            or 1.0
        )

        painter.setPen(QPen(self._AXIS, 1.2))
        painter.drawLine(int(center), int(top), int(center), int(top + height))
        painter.setPen(self._MUTED)
        painter.setFont(self._font())
        painter.drawText(
            QRectF(left, 0, width, 16),
            Qt.AlignmentFlag.AlignHCenter,
            "Pérdidas  ←  0  →  Ganancias",
        )

        for index, point in enumerate(self._points):
            y = top + row_height * index
            bar_height = max(7.0, min(15.0, row_height * 0.34))
            mid_y = y + row_height / 2
            gain_width = half * abs(float(point.positive)) / maximum
            loss_width = half * abs(float(point.negative)) / maximum

            painter.setFont(self._font())
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(6, y, left - 12, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                point.label[:18],
            )
            painter.setPen(Qt.PenStyle.NoPen)
            if loss_width > 0:
                loss_gradient = QLinearGradient(center - loss_width, 0, center, 0)
                loss_gradient.setColorAt(0.0, self._LOSS.lighter(118))
                loss_gradient.setColorAt(1.0, self._LOSS)
                painter.setBrush(loss_gradient)
                painter.drawRoundedRect(
                    QRectF(center - loss_width, mid_y - bar_height / 2, loss_width, bar_height),
                    5,
                    5,
                )
            if gain_width > 0:
                gain_gradient = QLinearGradient(center, 0, center + gain_width, 0)
                gain_gradient.setColorAt(0.0, self._GAIN)
                gain_gradient.setColorAt(1.0, self._GAIN.lighter(118))
                painter.setBrush(gain_gradient)
                painter.drawRoundedRect(
                    QRectF(center, mid_y - bar_height / 2, gain_width, bar_height),
                    5,
                    5,
                )

            tooltip = build_chart_tooltip(
                point.label,
                (
                    ("Ganancias", self._formatter(point.positive)),
                    ("Pérdidas", self._formatter(point.negative)),
                    ("Neto", self._formatter(point.value)),
                ),
                note="Descomposición del resultado acumulado por la dimensión mostrada.",
            )
            self._tooltip_regions.append(
                (QRectF(0, y, self.width(), row_height), tooltip)
            )
            painter.setFont(self._font(bold=True))
            painter.setPen(self._GAIN if point.value >= 0 else self._LOSS)
            painter.drawText(
                QRectF(left + width + 5, y, right - 8, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                self._formatter(point.value),
            )

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        show_chart_tooltip(self, event, self._tooltip_regions)
        super().mouseMoveEvent(event)

