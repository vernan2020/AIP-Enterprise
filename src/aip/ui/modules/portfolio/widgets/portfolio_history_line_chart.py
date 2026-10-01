from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget


class PortfolioHistoryLineChart(QWidget):
    """Compact institutional line chart for one historical portfolio KPI."""

    def __init__(
        self,
        *,
        value_formatter: Callable[[Decimal], str] | None = None,
        reference_value: Decimal | None = None,
        reference_label: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._points: tuple[tuple[date, Decimal | None], ...] = ()
        self._formatter = value_formatter or (lambda value: f"{value:,.2f}")
        self._previous_month_value: Decimal | None = None
        self._year_end_value: Decimal | None = None
        self._reference_value = reference_value
        self._reference_label = reference_label or "Referencia"
        self._hover_points: tuple[tuple[QPointF, date, Decimal], ...] = ()
        self._active_hover: tuple[QPointF, date, Decimal] | None = None
        self.setMinimumHeight(245)
        self.setMouseTracking(True)

    def set_data(
        self,
        points: tuple[tuple[date, Decimal | None], ...],
        *,
        previous_month_value: Decimal | None = None,
        year_end_value: Decimal | None = None,
    ) -> None:
        self._points = tuple(points)
        self._previous_month_value = previous_month_value
        self._year_end_value = year_end_value
        self._hover_points = ()
        self._active_hover = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        valid = [(cutoff, value) for cutoff, value in self._points if value is not None]
        if not valid:
            self._hover_points = ()
            painter.setPen(QColor("#718096"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        left = 64.0
        right = 18.0
        top = 86.0
        bottom = 30.0
        plot_width = max(30.0, self.width() - left - right)
        plot_height = max(30.0, self.height() - top - bottom)

        values = [float(value) for _, value in valid if value is not None]
        if self._reference_value is not None:
            values.append(float(self._reference_value))
        minimum = min(values)
        maximum = max(values)
        spread = maximum - minimum
        padding = max(abs(maximum) * 0.04, spread * 0.12, 0.01)
        y_min = minimum - padding
        y_max = maximum + padding
        if y_max <= y_min:
            y_max = y_min + 1.0

        grid_pen = QPen(QColor("#EDF2F7"))
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

        if self._reference_value is not None:
            reference_ratio = (float(self._reference_value) - y_min) / (y_max - y_min)
            reference_y = top + plot_height * (1.0 - reference_ratio)
            reference_pen = QPen(QColor("#9B6A00"))
            reference_pen.setWidthF(1.2)
            reference_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(reference_pen)
            painter.drawLine(
                QPointF(left, reference_y),
                QPointF(left + plot_width, reference_y),
            )
            painter.setPen(QColor("#7A5300"))
            painter.drawText(
                QRectF(left + 4, reference_y - 18, plot_width - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self._reference_label,
            )

        coordinates: list[QPointF] = []
        hover_points: list[tuple[QPointF, date, Decimal]] = []
        count = len(valid)
        for index, (cutoff, point_value) in enumerate(valid):
            assert point_value is not None
            x_ratio = index / max(1, count - 1)
            y_ratio = (float(point_value) - y_min) / (y_max - y_min)
            x = left + plot_width * x_ratio
            y = top + plot_height * (1.0 - y_ratio)
            coordinate = QPointF(x, y)
            coordinates.append(coordinate)
            hover_points.append((coordinate, cutoff, point_value))
        self._hover_points = tuple(hover_points)

        path = self._smooth_path(coordinates)

        area_path = QPainterPath()
        area_path.addPath(path)
        area_path.lineTo(coordinates[-1].x(), top + plot_height)
        area_path.lineTo(coordinates[0].x(), top + plot_height)
        area_path.closeSubpath()
        gradient = QLinearGradient(0.0, top, 0.0, top + plot_height)
        gradient.setColorAt(0.0, QColor(31, 90, 138, 52))
        gradient.setColorAt(0.70, QColor(31, 90, 138, 18))
        gradient.setColorAt(1.0, QColor(31, 90, 138, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(area_path)

        line_pen = QPen(QColor("#1F5A8A"))
        line_pen.setWidthF(2.4)
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(line_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1F5A8A"))
        marker_step = max(1, len(coordinates) // 12)
        for index, coordinate in enumerate(coordinates[:-1]):
            if index % marker_step == 0:
                painter.drawEllipse(coordinate, 2.5, 2.5)

        if self._active_hover is not None:
            active_point = self._active_hover[0]
            hover_pen = QPen(QColor(31, 90, 138, 90))
            hover_pen.setWidthF(1.0)
            hover_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(hover_pen)
            painter.drawLine(
                QPointF(active_point.x(), top),
                QPointF(active_point.x(), top + plot_height),
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(31, 90, 138, 36))
            painter.drawEllipse(active_point, 7.5, 7.5)
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawEllipse(active_point, 4.8, 4.8)
            painter.setBrush(QColor("#1F5A8A"))
            painter.drawEllipse(active_point, 3.0, 3.0)

        latest_coordinate = coordinates[-1]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(31, 90, 138, 40))
        painter.drawEllipse(latest_coordinate, 7.0, 7.0)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(latest_coordinate, 4.5, 4.5)
        painter.setBrush(QColor("#1F5A8A"))
        painter.drawEllipse(latest_coordinate, 2.8, 2.8)

        painter.setPen(QColor("#718096"))
        axis_indices = self._axis_label_indices(len(valid))
        label_width = min(72.0, max(52.0, plot_width / max(1, len(axis_indices))))
        for axis_position, index in enumerate(axis_indices):
            coordinate = coordinates[index]
            alignment = Qt.AlignmentFlag.AlignCenter
            label_left = coordinate.x() - label_width / 2
            if axis_position == 0:
                alignment = Qt.AlignmentFlag.AlignLeft
                label_left = left
            elif axis_position == len(axis_indices) - 1:
                alignment = Qt.AlignmentFlag.AlignRight
                label_left = left + plot_width - label_width
            painter.drawText(
                QRectF(label_left, top + plot_height + 7, label_width, 18),
                alignment,
                valid[index][0].strftime("%b-%y"),
            )

        latest = valid[-1][1]
        assert latest is not None
        latest_width = min(190.0, plot_width * 0.34)
        latest_rect = QRectF(left + plot_width - latest_width, 3, latest_width, 46)

        latest_label_font = QFont(self.font())
        latest_label_font.setPointSize(7)
        latest_label_font.setBold(True)
        painter.setFont(latest_label_font)
        painter.setPen(QColor("#718096"))
        painter.drawText(
            QRectF(latest_rect.left(), 2, latest_rect.width(), 14),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "ACTUAL",
        )

        header_font = QFont(self.font())
        header_font.setPointSize(12)
        header_font.setBold(True)
        painter.setFont(header_font)
        painter.setPen(QColor("#17324D"))
        painter.drawText(
            QRectF(latest_rect.left(), 15, latest_rect.width(), 28),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self._formatter(latest),
        )

        chip_width = min(205.0, max(130.0, plot_width * 0.46))
        self._draw_comparison_chip(
            painter,
            QRectF(left, 3, chip_width, 24),
            self._comparison_text("Mes ant.", latest, self._previous_month_value),
        )
        self._draw_comparison_chip(
            painter,
            QRectF(left, 31, chip_width, 24),
            self._comparison_text("Dic-25", latest, self._year_end_value),
        )

        minimum_value = min(value for _, value in valid if value is not None)
        maximum_value = max(value for _, value in valid if value is not None)
        comparison_font = QFont(self.font())
        comparison_font.setPointSize(8)
        painter.setFont(comparison_font)
        painter.setPen(QColor("#718096"))
        painter.drawText(
            QRectF(left, 59, plot_width, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"Mín {self._formatter(minimum_value)} · Máx {self._formatter(maximum_value)}",
        )

    @staticmethod
    def _axis_label_indices(point_count: int, *, max_labels: int = 5) -> tuple[int, ...]:
        if point_count <= 0:
            return ()
        if point_count <= max_labels:
            return tuple(range(point_count))
        last = point_count - 1
        raw = [round(last * step / (max_labels - 1)) for step in range(max_labels)]
        indices: list[int] = []
        for index in raw:
            if not indices or index != indices[-1]:
                indices.append(index)
        if indices[-1] != last:
            indices[-1] = last
        return tuple(indices)

    def _draw_comparison_chip(
        self,
        painter: QPainter,
        rect: QRectF,
        text: str,
    ) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#F3F6F9"))
        painter.drawRoundedRect(rect, 7.0, 7.0)

        chip_font = QFont(self.font())
        chip_font.setPointSize(8)
        chip_font.setBold(True)
        painter.setFont(chip_font)
        painter.setPen(QColor("#526678"))
        painter.drawText(
            rect.adjusted(9, 0, -9, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )

    @staticmethod
    def _smooth_path(coordinates: list[QPointF]) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(coordinates[0])
        if len(coordinates) == 1:
            return path
        for previous, current in zip(coordinates, coordinates[1:]):
            delta = (current.x() - previous.x()) * 0.42
            path.cubicTo(
                QPointF(previous.x() + delta, previous.y()),
                QPointF(current.x() - delta, current.y()),
                current,
            )
        return path

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._hover_points:
            self._active_hover = None
            super().mouseMoveEvent(event)
            return
        cursor = event.position()
        nearest = min(self._hover_points, key=lambda item: abs(item[0].x() - cursor.x()))
        x_distance = abs(nearest[0].x() - cursor.x())
        if x_distance <= 18.0:
            if self._active_hover != nearest:
                self._active_hover = nearest
                self.update()
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{nearest[1].strftime('%d/%m/%Y')}\n{self._formatter(nearest[2])}",
                self,
            )
        else:
            if self._active_hover is not None:
                self._active_hover = None
                self.update()
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._active_hover = None
        self.update()
        QToolTip.hideText()
        super().leaveEvent(event)

    def _axis_label(self, value: Decimal) -> str:
        formatted = self._formatter(value)
        return formatted.replace("₡", "").replace(" MM", "")

    def _signed(self, value: Decimal) -> str:
        prefix = "+" if value > 0 else ""
        return f"{prefix}{self._formatter(value)}"

    @staticmethod
    def _percentage_change(latest: Decimal, baseline: Decimal | None) -> Decimal | None:
        if baseline is None or baseline == 0:
            return None
        return ((latest - baseline) / abs(baseline)) * Decimal("100")

    def _comparison_text(
        self,
        label: str,
        latest: Decimal,
        baseline: Decimal | None,
    ) -> str:
        if baseline is None:
            return f"{label}: N/D"
        delta = latest - baseline
        percentage = self._percentage_change(latest, baseline)
        percentage_text = "N/D" if percentage is None else f"{percentage:+.1f}%"
        return f"{label}: {self._signed(delta)} ({percentage_text})"
