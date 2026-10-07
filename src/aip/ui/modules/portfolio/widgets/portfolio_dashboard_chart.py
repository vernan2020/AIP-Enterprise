from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from aip.ui.modules.portfolio.models.portfolio_dashboard_point import PortfolioDashboardPoint


class PortfolioDashboardBarChart(QWidget):
    """Executive ranked lollipop chart for concentration and opportunity lists."""

    _TEXT = QColor("#17324D")
    _MUTED = QColor("#6F8090")
    _GRID = QColor("#E7EEF3")
    _ACCENT = QColor("#176895")
    _ACCENT_LIGHT = QColor("#77B7D2")
    _BAR_PALETTE = (
        QColor("#0B5BC4"),
        QColor("#1EA7E1"),
        QColor("#11B8B0"),
        QColor("#30C77B"),
        QColor("#FF8A18"),
        QColor("#7C5CE6"),
        QColor("#E55391"),
        QColor("#5A78D6"),
        QColor("#27A2D8"),
        QColor("#9CAFC2"),
    )

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

        left, right, top, bottom = 142.0, 98.0, 16.0, 14.0
        width = max(50.0, self.width() - left - right)
        height = max(50.0, self.height() - top - bottom)
        row_height = height / max(1, len(self._points))
        maximum = max((abs(float(point.value)) for point in self._points), default=0.0) or 1.0

        for fraction in (0.25, 0.50, 0.75, 1.0):
            x = left + width * fraction
            painter.setPen(QPen(self._GRID, 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(x, top), QPointF(x, top + height))

        label_font = QFont(self.font())
        label_font.setPointSize(8)
        value_font = QFont(label_font)
        value_font.setBold(True)

        for index, point in enumerate(self._points):
            y = top + row_height * index + row_height / 2.0
            numeric = abs(float(point.value))
            x_end = left + width * numeric / maximum

            painter.setFont(label_font)
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(26, y - row_height / 2, left - 34, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                point.label[:22],
            )

            if index < 3:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#E8F1F6"))
                painter.drawEllipse(QPointF(11.0, y), 8.5, 8.5)
                painter.setFont(value_font)
                painter.setPen(QColor("#15577D"))
                painter.drawText(
                    QRectF(2, y - 9, 18, 18),
                    Qt.AlignmentFlag.AlignCenter,
                    str(index + 1),
                )

            bar_height = max(10.0, min(18.0, row_height * 0.52))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._BAR_PALETTE[index % len(self._BAR_PALETTE)])
            painter.drawRoundedRect(
                QRectF(left, y - bar_height / 2, max(4.0, x_end - left), bar_height),
                4,
                4,
            )

            painter.setFont(value_font)
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(left + width + 5, y - row_height / 2, right - 8, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                self._formatter(point.value),
            )


class PortfolioDashboardColumnChart(QWidget):
    """Executive vertical column chart for duration/allocation buckets."""

    _TEXT = QColor("#17324D")
    _MUTED = QColor("#6F8090")
    _GRID = QColor("#E7EEF3")
    _PALETTE = (
        QColor("#0B5BC4"),
        QColor("#1EA7E1"),
        QColor("#11B8B0"),
        QColor("#30C77B"),
        QColor("#FF8A18"),
        QColor("#7C5CE6"),
    )

    def __init__(
        self,
        *,
        value_formatter: Callable[[Decimal], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._points: tuple[PortfolioDashboardPoint, ...] = ()
        self._formatter = value_formatter or (lambda value: f"{value:,.1f}%")
        self.setMinimumHeight(240)

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

        left, right, top, bottom = 52.0, 16.0, 34.0, 54.0
        width = max(80.0, self.width() - left - right)
        height = max(80.0, self.height() - top - bottom)
        maximum = max((abs(float(point.value)) for point in self._points), default=0.0) or 1.0

        for fraction in (0.25, 0.50, 0.75, 1.0):
            y = top + height * (1.0 - fraction)
            painter.setPen(QPen(self._GRID, 1))
            painter.drawLine(QPointF(left, y), QPointF(left + width, y))

        slot = width / max(1, len(self._points))
        bar_width = min(64.0, slot * 0.58)
        label_font = QFont(self.font())
        label_font.setPointSize(8)
        value_font = QFont(label_font)
        value_font.setBold(True)

        for index, point in enumerate(self._points):
            numeric = abs(float(point.value))
            h = height * numeric / maximum
            x = left + slot * index + (slot - bar_width) / 2
            y = top + height - h
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._PALETTE[index % len(self._PALETTE)])
            painter.drawRoundedRect(QRectF(x, y, bar_width, max(3.0, h)), 5, 5)

            painter.setFont(value_font)
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(x - 18, max(4.0, y - 28), bar_width + 36, 24),
                Qt.AlignmentFlag.AlignCenter,
                self._formatter(point.value),
            )
            painter.setFont(label_font)
            painter.drawText(
                QRectF(left + slot * index, top + height + 8, slot, 34),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                point.label[:16],
            )


class PortfolioDashboardDonutChart(QWidget):
    """Modern compact donut for small portfolio composition sets."""

    _TEXT = QColor("#17324D")
    _MUTED = QColor("#6F8090")
    _TRACK = QColor("#EDF2F6")
    _PALETTE = (
        QColor("#145D8A"),
        QColor("#2C8EBB"),
        QColor("#54B8C4"),
        QColor("#8BC9B8"),
        QColor("#B8D9A0"),
    )

    def __init__(
        self,
        *,
        value_formatter: Callable[[Decimal], str] | None = None,
        center_label: str = "Distribución",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._points: tuple[PortfolioDashboardPoint, ...] = ()
        self._formatter = value_formatter or (lambda value: f"{value:,.1f}%")
        self._center_label = center_label
        self._center_value = "100%"
        self.setMinimumHeight(220)

    def set_data(self, points: tuple[PortfolioDashboardPoint, ...]) -> None:
        self._points = tuple(point for point in points if point.value >= 0)
        self.update()

    def set_center_value(self, value: str) -> None:
        self._center_value = value
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

        total = sum((float(point.value) for point in self._points), 0.0)
        if total <= 0:
            painter.setPen(self._MUTED)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        diameter = min(self.height() - 34.0, self.width() * 0.42, 210.0)
        diameter = max(110.0, diameter)
        left = 22.0
        top = (self.height() - diameter) / 2.0
        ring = QRectF(left, top, diameter, diameter)

        pen = QPen(self._TRACK, max(14.0, diameter * 0.12))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(ring, 0, 360 * 16)

        start_angle = 90 * 16
        for index, point in enumerate(self._points):
            span = -int(round((float(point.value) / total) * 360.0 * 16.0))
            segment_pen = QPen(
                self._PALETTE[index % len(self._PALETTE)],
                max(14.0, diameter * 0.12),
            )
            segment_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(segment_pen)
            painter.drawArc(ring, start_angle, span)
            start_angle += span

        center = ring.center()
        title_font = QFont(self.font())
        title_font.setPointSize(8)
        painter.setFont(title_font)
        painter.setPen(self._MUTED)
        painter.drawText(
            QRectF(center.x() - 54, center.y() - 22, 108, 18),
            Qt.AlignmentFlag.AlignCenter,
            self._center_label,
        )
        value_font = QFont(self.font())
        value_font.setPointSize(13)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.setPen(self._TEXT)
        painter.drawText(
            QRectF(center.x() - 60, center.y() - 3, 120, 28),
            Qt.AlignmentFlag.AlignCenter,
            self._center_value,
        )

        legend_left = left + diameter + 34.0
        legend_width = max(120.0, self.width() - legend_left - 12.0)
        row_height = min(34.0, (self.height() - 24.0) / max(1, len(self._points)))
        label_font = QFont(self.font())
        label_font.setPointSize(8)
        value_font = QFont(label_font)
        value_font.setBold(True)
        for index, point in enumerate(self._points):
            y = 12.0 + row_height * index
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._PALETTE[index % len(self._PALETTE)])
            painter.drawEllipse(QPointF(legend_left + 6, y + row_height / 2), 5, 5)

            painter.setFont(label_font)
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(legend_left + 18, y, legend_width * 0.62, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                point.label[:24],
            )
            painter.setFont(value_font)
            painter.drawText(
                QRectF(
                    legend_left + legend_width * 0.62,
                    y,
                    legend_width * 0.38,
                    row_height,
                ),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                self._formatter(point.value),
            )
