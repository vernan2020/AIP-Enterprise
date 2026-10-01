from __future__ import annotations

from decimal import Decimal
from math import fsum

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationBreakdownDisplay,
    PortfolioValuationComparisonDisplay,
    PortfolioValuationComparisonDisplayRow,
)


def _money(value: Decimal | None, currency: str | None = None) -> str:
    if value is None:
        return "N/D"
    prefix = ""
    if currency == "CRC":
        prefix = "₡"
    elif currency == "USD":
        prefix = "$"
    return f"{prefix}{value / Decimal('1000000'):,.2f} MM"


class _HorizontalBarChart(QWidget):
    def __init__(self, *, loss: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loss = loss
        self._items: tuple[tuple[str, Decimal, str], ...] = ()
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, items: tuple[tuple[str, Decimal, str], ...]) -> None:
        self._items = items
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        if not self._items:
            painter.setPen(QColor("#7B8B99"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        max_value = max(abs(value) for _label, value, _currency in self._items) or Decimal("1")
        label_width = min(150, max(95, int(rect.width() * 0.22)))
        value_width = min(115, max(88, int(rect.width() * 0.18)))
        plot_left = label_width + 8
        plot_right = rect.width() - value_width - 8
        plot_width = max(40, plot_right - plot_left)
        row_height = max(24, int((rect.height() - 12) / max(1, len(self._items))))
        bar_color = QColor("#F26B6B" if self._loss else "#45C36B")
        text_color = QColor("#B42318" if self._loss else "#16794B")

        painter.setFont(QFont("Segoe UI", 9))
        for index, (label, value, currency) in enumerate(self._items):
            center_y = 8 + index * row_height + row_height / 2
            bar_width = plot_width * float(abs(value) / max_value)
            bar_rect = QRectF(
                plot_right - bar_width if self._loss else plot_left,
                center_y - 7,
                bar_width,
                14,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bar_color)
            painter.drawRoundedRect(bar_rect, 4, 4)

            painter.setPen(QColor("#17324D"))
            painter.drawText(
                QRectF(4, center_y - 11, label_width, 22),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )
            painter.setPen(text_color)
            painter.drawText(
                QRectF(plot_right + 7, center_y - 11, value_width - 8, 22),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                _money(value, currency),
            )


class _DonutChart(QWidget):
    _COLORS = (
        QColor("#45C36B"),
        QColor("#EF6B6B"),
        QColor("#55A7E8"),
        QColor("#F0B54A"),
        QColor("#8B78D1"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: tuple[PortfolioValuationBreakdownDisplay, ...] = ()
        self.setMinimumHeight(180)

    def set_data(self, items: tuple[PortfolioValuationBreakdownDisplay, ...]) -> None:
        self._items = items
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        if not self._items:
            painter.setPen(QColor("#7B8B99"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        counts = [max(0, item.position_count) for item in self._items[:5]]
        total = fsum(counts)
        if total <= 0:
            painter.setPen(QColor("#7B8B99"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        diameter = min(rect.height() - 24, int(rect.width() * 0.42), 150)
        donut_rect = QRectF(14, (rect.height() - diameter) / 2, diameter, diameter)
        start_angle = 90 * 16
        for index, count in enumerate(counts):
            span = -int(360 * 16 * (count / total))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._COLORS[index % len(self._COLORS)])
            painter.drawPie(donut_rect, start_angle, span)
            start_angle += span

        inner = donut_rect.adjusted(
            diameter * 0.27,
            diameter * 0.27,
            -diameter * 0.27,
            -diameter * 0.27,
        )
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(inner)
        painter.setPen(QColor("#17324D"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(inner, Qt.AlignmentFlag.AlignCenter, f"{int(total)}\nposiciones")

        legend_x = int(donut_rect.right()) + 18
        painter.setFont(QFont("Segoe UI", 9))
        for index, item in enumerate(self._items[:5]):
            y = 30 + index * 28
            painter.setBrush(self._COLORS[index % len(self._COLORS)])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(legend_x, y + 3, 9, 9))
            painter.setPen(QColor("#17324D"))
            share = item.position_count / total * 100
            painter.drawText(
                QRectF(legend_x + 16, y - 2, rect.width() - legend_x - 20, 20),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"{item.label} · {item.position_count} · {share:.1f}%",
            )


class _IssuerNetChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: tuple[PortfolioValuationBreakdownDisplay, ...] = ()
        self.setMinimumHeight(180)

    def set_data(self, items: tuple[PortfolioValuationBreakdownDisplay, ...]) -> None:
        self._items = items[:5]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        if not self._items:
            painter.setPen(QColor("#7B8B99"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        max_value = max(abs(item.net) for item in self._items) or Decimal("1")
        center_x = int(rect.width() * 0.5)
        plot_half = max(50, int(rect.width() * 0.28))
        label_width = max(100, center_x - plot_half - 12)
        row_height = max(25, int((rect.height() - 12) / len(self._items)))
        painter.setPen(QPen(QColor("#CCD8E3"), 1))
        painter.drawLine(center_x, 8, center_x, rect.height() - 8)

        painter.setFont(QFont("Segoe UI", 9))
        for index, item in enumerate(self._items):
            center_y = 8 + index * row_height + row_height / 2
            width = plot_half * float(abs(item.net) / max_value)
            positive = item.net >= 0
            bar_rect = QRectF(
                center_x if positive else center_x - width,
                center_y - 7,
                width,
                14,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#45C36B" if positive else "#EF6B6B"))
            painter.drawRoundedRect(bar_rect, 3, 3)
            painter.setPen(QColor("#17324D"))
            painter.drawText(
                QRectF(4, center_y - 11, label_width, 22),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                item.label,
            )
            painter.setPen(QColor("#16794B" if positive else "#B42318"))
            value_text = f"{item.net / Decimal('1000000'):+,.2f} MM"
            painter.drawText(
                QRectF(center_x + plot_half + 8, center_y - 11, 105, 22),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                value_text,
            )


class PortfolioValuationComparisonView(QWidget):
    """Graphical view of authoritative accumulated valuation from the Master."""

    _GAIN = QColor("#16794B")
    _LOSS = QColor("#B42318")
    _NEUTRAL = QColor("#22384C")

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("portfolioValuationComparison")
        self.setStyleSheet("""
            QWidget#portfolioValuationComparison { background:#F7F9FC; }
            QFrame[valuationCard="true"] {
                background:#FFFFFF;
                border:1px solid #DEE7EF;
                border-radius:10px;
            }
            QGroupBox[valuationPanel="true"] {
                background:#FFFFFF;
                border:1px solid #DEE7EF;
                border-radius:10px;
                margin-top:16px;
                font-weight:700;
                color:#17324D;
            }
            QGroupBox[valuationPanel="true"]::title {
                subcontrol-origin:margin;
                left:12px;
                padding:0 5px;
            }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(9)

        self._note = QLabel()
        self._note.setWordWrap(True)
        self._note.setStyleSheet(
            "background:#EEF6FF; color:#24577F; border:1px solid #D5E8F8; "
            "border-radius:7px; padding:7px 10px;"
        )
        layout.addWidget(self._note)

        self._cards = QGridLayout()
        self._cards.setHorizontalSpacing(8)
        self._cards.setVerticalSpacing(8)
        self._card_values: dict[str, QLabel] = {}
        card_defs = (
            ("gain", "Ganancia total", "#16794B"),
            ("loss", "Pérdida total", "#B42318"),
            ("net", "Resultado neto", "#16794B"),
            ("gain_count", "Posiciones con ganancia", "#16794B"),
            ("loss_count", "Posiciones con pérdida", "#B42318"),
        )
        for index, (key, title, color) in enumerate(card_defs):
            self._cards.addWidget(self._metric_card(key, title, color), 0, index)
        layout.addLayout(self._cards)

        charts = QGridLayout()
        charts.setHorizontalSpacing(9)
        charts.setVerticalSpacing(9)

        gain_group = self._panel("Top 5 ganancias")
        gain_layout = QVBoxLayout(gain_group)
        self._gain_chart = _HorizontalBarChart(loss=False)
        gain_layout.addWidget(self._gain_chart)
        charts.addWidget(gain_group, 0, 0, 1, 2)

        loss_group = self._panel("Top 5 pérdidas")
        loss_layout = QVBoxLayout(loss_group)
        self._loss_chart = _HorizontalBarChart(loss=True)
        loss_layout.addWidget(self._loss_chart)
        charts.addWidget(loss_group, 0, 2, 1, 2)

        currency_group = self._panel("Distribución de posiciones por moneda")
        currency_layout = QVBoxLayout(currency_group)
        self._currency_chart = _DonutChart()
        currency_layout.addWidget(self._currency_chart)
        charts.addWidget(currency_group, 1, 0)

        issuer_group = self._panel("Ganancia / pérdida neta por emisor y moneda · Top 5")
        issuer_layout = QVBoxLayout(issuer_group)
        self._issuer_chart = _IssuerNetChart()
        issuer_layout.addWidget(self._issuer_chart)
        charts.addWidget(issuer_group, 1, 1, 1, 2)

        detail_group = self._panel("Detalle por posición · Top 10")
        detail_layout = QVBoxLayout(detail_group)
        self._positions = self._table(
            ["Posición / ISIN", "Emisor", "Moneda", "Valuación acumulada"]
        )
        self._positions.setObjectName("portfolioValuationPositions")
        self._positions.setMinimumHeight(180)
        detail_layout.addWidget(self._positions)
        charts.addWidget(detail_group, 1, 3)

        for column in range(4):
            charts.setColumnStretch(column, 1)
        layout.addLayout(charts, 1)

    def _metric_card(self, key: str, title: str, color: str) -> QFrame:
        card = QFrame()
        card.setProperty("valuationCard", True)
        card.setMinimumHeight(76)
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 9, 12, 9)
        box.setSpacing(3)
        caption = QLabel(title)
        caption.setStyleSheet("color:#526678; font-size:9px; border:none;")
        value = QLabel("N/D")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        value.setFont(font)
        value.setStyleSheet(f"color:{color}; border:none;")
        helper = QLabel("")
        helper.setObjectName(f"{key}Helper")
        helper.setStyleSheet("color:#7B8B99; font-size:8px; border:none;")
        box.addWidget(caption)
        box.addWidget(value)
        box.addWidget(helper)
        self._card_values[key] = value
        return card

    @staticmethod
    def _panel(title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setProperty("valuationPanel", True)
        return group

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def bind(self, model: PortfolioValuationComparisonDisplay, valuation_date: str) -> None:
        mixed_currency = len(model.currency_breakdown) > 1
        suffix = (
            " Totales monetarios globales se mantienen N/D porque existen varias monedas "
            "y no se aplica una conversión cambiaria no certificada."
            if mixed_currency
            else ""
        )
        self._note.setText(
            f"Corte {valuation_date} · Ganancia / pérdida usa directamente Valuación "
            "Acumulada del Maestro de Inversiones. Los agregados son sumas del campo "
            f"fuente; no se deriva valor de mercado menos valor contable.{suffix}"
        )

        currency = model.currency_breakdown[0].label if len(model.currency_breakdown) == 1 else None
        self._card_values["gain"].setText(_money(model.gain_total, currency))
        self._card_values["loss"].setText(_money(model.loss_total, currency))
        self._card_values["net"].setText(_money(model.net_total, currency))
        self._card_values["gain_count"].setText(str(model.gain_count))
        self._card_values["loss_count"].setText(str(model.loss_count))

        total = model.available_count
        self._set_helper("gain", f"{model.gain_count} posiciones con valor positivo")
        self._set_helper("loss", f"{model.loss_count} posiciones con valor negativo")
        self._set_helper("net", f"{total} posiciones con Valuación Acumulada disponible")
        self._set_helper(
            "gain_count",
            f"{(model.gain_count / total * 100):.1f}% del total" if total else "N/D",
        )
        self._set_helper(
            "loss_count",
            f"{(model.loss_count / total * 100):.1f}% del total" if total else "N/D",
        )

        positive = sorted(
            (row for row in model.positions if row.value is not None and row.value > 0),
            key=lambda row: row.value or Decimal("0"),
            reverse=True,
        )[:5]
        negative = sorted(
            (row for row in model.positions if row.value is not None and row.value < 0),
            key=lambda row: row.value or Decimal("0"),
        )[:5]
        self._gain_chart.set_data(tuple(self._chart_item(row) for row in positive))
        self._loss_chart.set_data(tuple(self._chart_item(row) for row in negative))
        self._currency_chart.set_data(model.currency_breakdown)
        self._issuer_chart.set_data(model.issuer_breakdown)
        self._populate_top_positions(model.positions)

    def _set_helper(self, key: str, value: str) -> None:
        helper = self.findChild(QLabel, f"{key}Helper")
        if helper is not None:
            helper.setText(value)

    @staticmethod
    def _chart_item(
        row: PortfolioValuationComparisonDisplayRow,
    ) -> tuple[str, Decimal, str]:
        return (
            row.cells[0],
            row.value or Decimal("0"),
            row.cells[2] if len(row.cells) > 2 else "",
        )

    def _populate_top_positions(
        self,
        rows: tuple[PortfolioValuationComparisonDisplayRow, ...],
    ) -> None:
        ranked = sorted(
            (row for row in rows if row.value is not None),
            key=lambda row: abs(row.value or Decimal("0")),
            reverse=True,
        )[:10]
        self._positions.setRowCount(len(ranked))
        for row_index, row in enumerate(ranked):
            values = (row.cells[0], row.cells[1], row.cells[2], row.cells[3])
            color = self._tone_color(row.tone)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if len(row.cells) > 5:
                    item.setToolTip(f"Fuente: {row.cells[5]}")
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
