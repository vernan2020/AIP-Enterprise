"""Presentation-only six-band SICVECA GAP chart for real validated XML sources."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from aip.product.configured.irrbb.regulatory_gap_six_band import (
    RegulatoryGapBucket,
    RegulatoryGapResult,
)


class RegulatoryGapChart(QWidget):
    """CRC regulatory GAP bars and cumulative line; never contractual ΔNII/ΔEVE."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rateRiskRegulatorySixBandChart")
        self.setMinimumHeight(228)
        self.setMaximumHeight(320)
        self.setMouseTracking(True)
        self._rows: tuple[RegulatoryGapBucket, ...] = ()
        self._status = "BLOCKED"

    def set_result(self, gap: RegulatoryGapResult) -> None:
        self._status = gap.status
        self._rows = gap.rows if gap.is_ready else ()
        self.setAccessibleName("GAP regulatorio por banda SICVECA")
        self.setAccessibleDescription(
            "Gráfico conciliado de GAP simple y acumulado en colones"
            if gap.is_ready
            else "Sin GAP conciliado; no se presentan estimaciones"
        )
        self.update()

    def _chart_bounds(self) -> tuple[float, float, float, float]:
        return (58.0, 50.0, max(70.0, self.width() - 82.0), max(92.0, self.height() - 98.0))

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#C7DDEB"), 1))
        painter.setBrush(QColor("#F7FAFD"))
        painter.drawRoundedRect(
            QRectF(1.0, 1.0, float(self.width() - 2), float(self.height() - 2)),
            10,
            10,
        )
        painter.setPen(QColor("#00345F"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(18, 23, "GAP simple por banda")
        painter.setPen(QColor("#00A9E0"))
        painter.drawText(184, 23, "●  GAP acumulado")
        if not self._rows:
            painter.setPen(QColor("#657C8D"))
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(20, 28, -20, -15),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                "Sin GAP regulatorio conciliado. Revise Brechas y Calce; no se asumen ceros.",
            )
            painter.end()
            return

        left, top, width, height = self._chart_bounds()
        middle = top + height / 2.0
        peak = max(
            [abs(row.gap_crc) for row in self._rows]
            + [abs(row.cumulative_gap_crc) for row in self._rows]
            + [Decimal("0")]
        )
        denominator = peak if peak else Decimal("1")
        for fraction in (-1.0, -0.5, 0.0, 0.5, 1.0):
            y = middle - (height * 0.43) * fraction
            painter.setPen(QPen(QColor("#BED5E3" if fraction == 0 else "#E0EAF1"), 1))
            painter.drawLine(QPointF(left, y), QPointF(left + width, y))

        step = width / len(self._rows)
        points: list[QPointF] = []
        for index, row in enumerate(self._rows):
            x = left + step * (index + 0.5)
            delta = float(row.gap_crc / denominator)
            accumulated = float(row.cumulative_gap_crc / denominator)
            y = middle - delta * height * 0.43
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#005EB8" if delta >= 0 else "#F2994A"))
            painter.drawRoundedRect(
                QRectF(x - step * 0.17, min(y, middle), step * 0.34, max(abs(y - middle), 1.5)),
                3,
                3,
            )
            points.append(QPointF(x, middle - accumulated * height * 0.43))
            painter.setPen(QColor("#566D7C"))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            labels = painter.fontMetrics()
            text = labels.elidedText(row.bucket_label, Qt.TextElideMode.ElideRight, int(step - 6))
            painter.drawText(
                QRectF(left + index * step, top + height + 12, step, 25),
                Qt.AlignmentFlag.AlignCenter,
                text,
            )

        if points:
            line = QPainterPath(points[0])
            for point in points[1:]:
                line.lineTo(point)
            painter.setPen(QPen(QColor("#00A9E0"), 2.5))
            painter.drawPath(line)
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.setBrush(QColor("#00A9E0"))
            for point in points:
                painter.drawEllipse(point, 4.0, 4.0)
        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._rows:
            left, _top, width, _height = self._chart_bounds()
            x = event.position().x()
            if left <= x < left + width:
                index = min(int((x - left) / (width / len(self._rows))), len(self._rows) - 1)
                row = self._rows[index]
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"{row.bucket_label} (CRC)\n"
                    f"GAP simple: {row.gap_crc:,.2f}\n"
                    f"GAP acumulado: {row.cumulative_gap_crc:,.2f}",
                    self,
                )
                return
        QToolTip.hideText()
        super().mouseMoveEvent(event)
