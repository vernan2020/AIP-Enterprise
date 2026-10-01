from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationBreakdownPoint,
    PortfolioValuationComparisonDisplay,
    PortfolioValuationComparisonDisplayRow,
)


_MILLION = Decimal("1000000")


def _format_mm(value: Decimal) -> str:
    return f"₡{value / _MILLION:,.2f} MM"


class _HorizontalValuationBars(QWidget):
    def __init__(self, *, loss_mode: bool = False) -> None:
        super().__init__()
        self._rows: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
        self._loss_mode = loss_mode
        self.setMinimumHeight(176)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_rows(self, rows: tuple[PortfolioValuationComparisonDisplayRow, ...]) -> None:
        self._rows = rows
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        if not self._rows:
            painter.setPen(QColor("#8A98A6"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        values = [abs(row.amount or Decimal("0")) for row in self._rows]
        maximum = max(values) if values else Decimal("0")
        if maximum <= 0:
            return

        left = 126
        right = 82
        top = 10
        row_height = max(25, (self.height() - 22) // max(1, len(self._rows)))
        available = max(40, self.width() - left - right)
        bar_color = QColor("#F07B7B" if self._loss_mode else "#44C767")
        text_color = QColor("#C62828" if self._loss_mode else "#168447")

        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)

        for index, row in enumerate(self._rows):
            amount = abs(row.amount or Decimal("0"))
            y = top + index * row_height
            label = row.cells[0] if row.cells else "N/D"
            painter.setPen(QColor("#22384C"))
            painter.drawText(4, y + 17, label[:20])

            ratio = float(amount / maximum) if maximum else 0.0
            width = max(2.0, available * ratio)
            x = left if not self._loss_mode else left + available - width
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bar_color)
            painter.drawRoundedRect(QRectF(x, y + 4, width, 14), 4, 4)

            painter.setPen(text_color)
            value_text = f"{amount / _MILLION:,.2f}"
            if self._loss_mode:
                value_text = f"-{value_text}"
            value_x = left + available + 8
            painter.drawText(value_x, y + 17, value_text)

        axis_pen = QPen(QColor("#D7E0E8"))
        axis_pen.setWidth(1)
        painter.setPen(axis_pen)
        painter.drawLine(left, self.height() - 5, left + available, self.height() - 5)


class _BreakdownBars(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._points: tuple[PortfolioValuationBreakdownPoint, ...] = ()
        self.setMinimumHeight(185)

    def set_points(self, points: tuple[PortfolioValuationBreakdownPoint, ...]) -> None:
        self._points = points[:5]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        if not self._points:
            painter.setPen(QColor("#8A98A6"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        max_abs = max(abs(point.amount) for point in self._points)
        if max_abs <= 0:
            return
        center = self.width() // 2
        label_width = 100
        chart_left = label_width + 8
        chart_right = self.width() - 84
        half = max(35, min(center - chart_left, chart_right - center))
        row_height = max(27, (self.height() - 16) // len(self._points))

        pen = QPen(QColor("#D7E0E8"))
        painter.setPen(pen)
        painter.drawLine(center, 6, center, self.height() - 8)

        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)

        for index, point in enumerate(self._points):
            y = 8 + index * row_height
            painter.setPen(QColor("#22384C"))
            painter.drawText(3, y + 17, point.label[:18])
            width = max(2.0, half * float(abs(point.amount) / max_abs))
            if point.amount >= 0:
                x = center
                color = QColor("#44C767")
                text_color = QColor("#168447")
            else:
                x = center - width
                color = QColor("#F07B7B")
                text_color = QColor("#C62828")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y + 4, width, 14), 3, 3)
            painter.setPen(text_color)
            painter.drawText(self.width() - 78, y + 17, _format_mm(point.amount))


class _CurrencyDonut(QWidget):
    _PALETTE = (
        QColor("#3CBF67"),
        QColor("#EF6B6B"),
        QColor("#5FA8E6"),
        QColor("#8E79D6"),
        QColor("#E5A54A"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._points: tuple[PortfolioValuationBreakdownPoint, ...] = ()
        self._net = Decimal("0")
        self.setMinimumHeight(185)

    def set_data(
        self,
        points: tuple[PortfolioValuationBreakdownPoint, ...],
        net: Decimal,
    ) -> None:
        self._points = points[:5]
        self._net = net
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        if not self._points:
            painter.setPen(QColor("#8A98A6"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        total = sum((abs(point.amount) for point in self._points), Decimal("0"))
        if total <= 0:
            return

        size = min(132, self.height() - 28, max(90, self.width() // 3))
        rect = QRectF(16, (self.height() - size) / 2, size, size)
        start_angle = 90 * 16
        for index, point in enumerate(self._points):
            span = int(float(abs(point.amount) / total) * 360 * 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._PALETTE[index % len(self._PALETTE)])
            painter.drawPie(rect, start_angle, -span)
            start_angle -= span

        inner = rect.adjusted(size * 0.25, size * 0.25, -size * 0.25, -size * 0.25)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(inner)

        center_font = QFont(self.font())
        center_font.setPointSize(8)
        center_font.setBold(True)
        painter.setFont(center_font)
        painter.setPen(QColor("#22384C"))
        painter.drawText(inner, Qt.AlignmentFlag.AlignCenter, _format_mm(self._net))

        legend_x = int(rect.right()) + 16
        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)
        for index, point in enumerate(self._points):
            y = 30 + index * 28
            color = self._PALETTE[index % len(self._PALETTE)]
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(legend_x, y - 8, 9, 9)
            painter.setPen(QColor("#22384C"))
            painter.drawText(legend_x + 15, y, point.label[:12])
            painter.setPen(QColor("#168447") if point.amount >= 0 else QColor("#C62828"))
            painter.drawText(legend_x + 72, y, _format_mm(point.amount))


class PortfolioValuationComparisonView(QWidget):
    """Visual dashboard of authoritative accumulated valuation from the Master."""

    _GAIN = QColor("#16794B")
    _LOSS = QColor("#B42318")
    _NEUTRAL = QColor("#22384C")

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("portfolioValuationComparison")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(8)

        self._note = QLabel(
            "Ganancia / pérdida usa directamente la columna Valuación Acumulada del "
            "Maestro de Inversiones. AIP no recalcula el indicador."
        )
        self._note.setWordWrap(True)
        self._note.setStyleSheet(
            "background:#F2F8FD; border:1px solid #C9E2F5; border-radius:6px; "
            "color:#356789; padding:7px 10px;"
        )
        layout.addWidget(self._note)

        self._summary_grid = QGridLayout()
        self._summary_grid.setHorizontalSpacing(8)
        self._summary_grid.setVerticalSpacing(8)
        self._summary_values: dict[str, QLabel] = {}
        self._summary_helpers: dict[str, QLabel] = {}
        definitions = (
            ("gain", "Ganancia total", "gain"),
            ("loss", "Pérdida total", "loss"),
            ("net", "Resultado neto", "neutral"),
            ("gain_count", "Posiciones con ganancia", "gain"),
            ("loss_count", "Posiciones con pérdida", "loss"),
        )
        for column, (key, title, tone) in enumerate(definitions):
            self._summary_grid.addWidget(self._summary_card(key, title, tone), 0, column)
        layout.addLayout(self._summary_grid)

        charts = QGridLayout()
        charts.setHorizontalSpacing(8)
        charts.setVerticalSpacing(8)

        gains_group = self._group("Top 5 ganancias")
        self._gains_chart = _HorizontalValuationBars()
        gains_group.layout().addWidget(self._gains_chart)
        charts.addWidget(gains_group, 0, 0)

        losses_group = self._group("Top 5 pérdidas")
        self._losses_chart = _HorizontalValuationBars(loss_mode=True)
        losses_group.layout().addWidget(self._losses_chart)
        charts.addWidget(losses_group, 0, 1)

        currency_group = self._group("Ganancia / pérdida por moneda")
        self._currency_chart = _CurrencyDonut()
        currency_group.layout().addWidget(self._currency_chart)
        charts.addWidget(currency_group, 1, 0)

        issuer_group = self._group("Ganancia / pérdida por emisor · Top 5")
        self._issuer_chart = _BreakdownBars()
        issuer_group.layout().addWidget(self._issuer_chart)
        charts.addWidget(issuer_group, 1, 1)

        layout.addLayout(charts)

        detail_group = self._group("Detalle por posición · Top 10 por magnitud")
        self._detail_caption = QLabel("")
        self._detail_caption.setObjectName("portfolioValuationDetailCaption")
        self._detail_caption.setStyleSheet("color:#617386; font-size:9px;")
        detail_group.layout().addWidget(self._detail_caption)
        self._positions = self._table(
            ["Posición / ISIN", "Emisor", "Moneda", "Ganancia / Pérdida (₡ MM)"]
        )
        self._positions.setObjectName("portfolioValuationPositions")
        self._positions.setMaximumHeight(255)
        detail_group.layout().addWidget(self._positions)
        layout.addWidget(detail_group)

    @staticmethod
    def _group(title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(
            "QGroupBox {border:1px solid #D7E0E8; border-radius:8px; margin-top:8px; "
            "font-weight:700; color:#22384C; background:#FFFFFF;} "
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )
        group.setLayout(QVBoxLayout())
        group.layout().setContentsMargins(8, 12, 8, 8)
        return group

    def _summary_card(self, key: str, title: str, tone: str) -> QFrame:
        card = QFrame()
        card.setObjectName(f"portfolioValuationSummary_{key}")
        background = "#F4FBF7"
        border = "#CFE8D8"
        value_color = "#168447"
        if tone == "loss":
            background = "#FFF6F6"
            border = "#F1D0D0"
            value_color = "#C62828"
        elif tone == "neutral":
            background = "#F7FAFC"
            border = "#D7E0E8"
            value_color = "#174E78"
        card.setStyleSheet(
            f"QFrame {{background:{background}; border:1px solid {border}; "
            "border-radius:8px;}"
        )
        box = QVBoxLayout(card)
        box.setContentsMargins(10, 7, 10, 7)
        box.setSpacing(2)
        caption = QLabel(title)
        caption.setStyleSheet("border:none; color:#314B60; font-size:9px; font-weight:600;")
        value = QLabel("N/D")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        value.setFont(font)
        value.setStyleSheet(f"border:none; color:{value_color};")
        helper = QLabel("")
        helper.setStyleSheet("border:none; color:#718496; font-size:8px;")
        box.addWidget(caption)
        box.addWidget(value)
        box.addWidget(helper)
        self._summary_values[key] = value
        self._summary_helpers[key] = helper
        return card

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def bind(self, model: PortfolioValuationComparisonDisplay, valuation_date: str) -> None:
        self._note.setText(
            f"Corte {valuation_date} · Ganancia / pérdida corresponde directamente a "
            "Valuación Acumulada del Maestro de Inversiones; no se realiza cálculo adicional."
        )
        total_count = model.gain_count + model.loss_count + model.neutral_count
        self._summary_values["gain"].setText(_format_mm(model.gain_total))
        self._summary_values["loss"].setText(_format_mm(model.loss_total))
        self._summary_values["net"].setText(_format_mm(model.net_total))
        self._summary_values["gain_count"].setText(str(model.gain_count))
        self._summary_values["loss_count"].setText(str(model.loss_count))

        self._summary_helpers["gain"].setText(
            self._count_helper(model.gain_count, total_count)
        )
        self._summary_helpers["loss"].setText(
            self._count_helper(model.loss_count, total_count)
        )
        self._summary_helpers["net"].setText(
            f"{total_count} posiciones con valuación disponible"
        )
        self._summary_helpers["gain_count"].setText(
            self._percentage_helper(model.gain_count, total_count)
        )
        self._summary_helpers["loss_count"].setText(
            self._percentage_helper(model.loss_count, total_count)
        )
        self._summary_values["net"].setStyleSheet(
            "border:none; font-weight:700; color:"
            + ("#168447;" if model.net_total >= 0 else "#C62828;")
        )

        self._gains_chart.set_rows(model.top_gains)
        self._losses_chart.set_rows(model.top_losses)
        self._currency_chart.set_data(model.currency_breakdown, model.net_total)
        self._issuer_chart.set_points(model.issuer_breakdown)

        ranked = sorted(
            (row for row in model.positions if row.amount is not None),
            key=lambda row: abs(row.amount or Decimal("0")),
            reverse=True,
        )[:10]
        self._populate_detail(ranked)
        self._detail_caption.setText(
            f"Mostrando {len(ranked)} de {len(model.positions)} posiciones. "
            "La tabla completa permanece disponible en la pestaña Posiciones."
        )

    @staticmethod
    def _count_helper(count: int, total: int) -> str:
        if total <= 0:
            return f"{count} posiciones"
        return f"{count} posiciones ({count / total * 100:.1f}%)"

    @staticmethod
    def _percentage_helper(count: int, total: int) -> str:
        if total <= 0:
            return "0.0% del total"
        return f"{count / total * 100:.1f}% del total"

    def _populate_detail(
        self,
        rows: list[PortfolioValuationComparisonDisplayRow],
    ) -> None:
        self._positions.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            amount = row.amount
            color = self._tone_color(row.tone)
            values = (
                row.cells[0],
                row.cells[1],
                row.cells[2],
                _format_mm(amount) if amount is not None else "N/D",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setForeground(color)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._positions.setItem(row_index, column, item)

    def _tone_color(self, tone: str) -> QColor:
        if tone == "gain":
            return self._GAIN
        if tone == "loss":
            return self._LOSS
        return self._NEUTRAL
