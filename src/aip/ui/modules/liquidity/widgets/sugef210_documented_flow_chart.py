"""Native Qt visualization of individually admitted SUGEF 2-10 cash events.

A missing schedule remains N/D, never a zero; CRC and USD use independent
scales to avoid suggesting that nominal amounts are comparable currencies.
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityProjectionResult,
)


class SUGEF210DocumentedFlowChart(QWidget):
    """Two native-currency panels for documented net cashflow events only."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sugef210DocumentedFlowChart")
        self.setAccessibleName("Flujo neto documentado por banda y moneda")
        self.setMinimumHeight(295)
        self._bands: tuple[str, ...] = ()
        self._series: dict[str, tuple[Decimal | None, ...]] = {
            "CRC": (),
            "USD": (),
        }
        self._status = "N/D — sin proyección aprobada"
        self.setToolTip(
            "Cada barra es el flujo neto de eventos admitidos en una banda. "
            "Los símbolos ? representan N/D, nunca importes cero. "
            "CRC y USD tienen escalas independientes."
        )

    def load_projection(self, projection: LiquidityProjectionResult | None) -> None:
        """Clear or validate all currency/band pairs before rendering."""
        if projection is None:
            self._bands = ()
            self._series = {"CRC": (), "USD": ()}
            self._status = "N/D — sin proyección aprobada"
            self.update()
            return
        indexed = {(row.window.key, row.currency): row for row in projection.rows}
        if len(indexed) != len(projection.rows) or len(indexed) != 2 * len(
            projection.windows
        ):
            raise ValueError("Incomplete or duplicate CRC/USD liquidity chart bands")
        self._bands = tuple(window.label for window in projection.windows)
        series: dict[str, tuple[Decimal | None, ...]] = {}
        for currency in ("CRC", "USD"):
            values: list[Decimal | None] = []
            for window in projection.windows:
                row = indexed.get((window.key, currency))
                if row is None:
                    raise ValueError("Liquidity chart currency/band pairing is incomplete")
                if not row.net_flow.is_finite():
                    raise ValueError("Liquidity chart cannot display nonfinite cashflows")
                values.append(
                    row.net_flow
                    if row.event_count > 0 or projection.certified_comprehensive
                    else None
                )
            series[currency] = tuple(values)
        self._series = series
        self._status = (
            f"{projection.scenario} · {projection.cutoff.isoformat()} · "
            "FLUJOS DOCUMENTADOS / NO CERTIFICADO"
        )
        self.update()

    def documented_bands(self, currency: str) -> int:
        if currency not in self._series:
            raise ValueError("Unknown currency")
        return sum(value is not None for value in self._series[currency])

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        painter.setPen(QColor("#17375E"))
        painter.drawText(16, 25, self._status)
        if not self._bands:
            painter.setPen(QColor("#778493"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "N/D")
            painter.end()
            return
        width = max(80, self.width() - 82)
        section_height = max(90, (self.height() - 48) // 2)
        for index, currency in enumerate(("CRC", "USD")):
            values = self._series[currency]
            top = 39 + index * section_height
            baseline = top + section_height // 2
            amplitude = max(13, section_height // 2 - 27)
            color = QColor("#1764A7" if currency == "CRC" else "#0E928E")
            painter.setPen(QColor("#17375E"))
            painter.drawText(16, top + 11, f"{currency} · neto parcial")
            painter.setPen(QPen(QColor("#C9D3E0"), 1))
            painter.drawLine(54, baseline, 54 + width, baseline)
            known = [abs(value) for value in values if value is not None]
            maximum = max(known) if known else Decimal(0)
            for band, value in enumerate(values):
                center = 54 + int((band + 0.5) * width / len(values))
                bar_width = max(4, int(width / (len(values) * 1.8)))
                if value is None:
                    painter.setPen(QColor("#98A4AF"))
                    painter.drawText(
                        QRectF(center - 8, baseline - 8, 16, 16),
                        Qt.AlignmentFlag.AlignCenter,
                        "?",
                    )
                    continue
                extent = (
                    int(Decimal(amplitude) * abs(value) / maximum)
                    if maximum > 0
                    else 0
                )
                if extent:
                    painter.fillRect(
                        QRectF(
                            center - bar_width / 2,
                            baseline - extent if value > 0 else baseline,
                            bar_width,
                            extent,
                        ),
                        color,
                    )
                painter.setPen(QColor("#738195"))
                painter.drawText(
                    QRectF(center - 9, top + section_height - 16, 18, 14),
                    Qt.AlignmentFlag.AlignCenter,
                    str(band + 1),
                )
        painter.end()
