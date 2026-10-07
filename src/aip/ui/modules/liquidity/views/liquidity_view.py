from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.liquidity.models.liquidity_row import LiquidityRow
from aip.ui.modules.liquidity.presenters.liquidity_presenter import LiquidityPresenter
from aip.ui.modules.liquidity.viewmodels.liquidity_view_model import LiquidityViewModel


class _LiquidityBarChart(QWidget):
    """Horizontal capsule chart for contractual liquidity buckets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: tuple[tuple[str, float], ...] = ()
        self.setMinimumHeight(250)

    def set_data(self, points: tuple[tuple[str, float], ...]) -> None:
        self._points = points
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

        left, right, top, bottom = 132.0, 108.0, 18.0, 18.0
        width = max(60.0, self.width() - left - right)
        height = max(60.0, self.height() - top - bottom)
        row_height = height / max(1, len(self._points))
        maximum = max((abs(value) for _, value in self._points), default=0.0) or 1.0

        label_font = QFont(self.font())
        label_font.setPointSize(8)
        value_font = QFont(label_font)
        value_font.setBold(True)

        for index, (label, value) in enumerate(self._points):
            y = top + index * row_height
            center_y = y + row_height / 2.0
            bar_height = max(12.0, min(22.0, row_height * 0.42))
            bar_width = width * abs(value) / maximum

            painter.setFont(label_font)
            painter.setPen(QColor("#23384B"))
            painter.drawText(
                QRectF(8, y, left - 18, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#EEF3F7"))
            painter.drawRoundedRect(
                QRectF(left, center_y - bar_height / 2, width, bar_height),
                bar_height / 2,
                bar_height / 2,
            )

            fill = QColor("#2479A8")
            gradient = QLinearGradient(left, 0, left + max(2.0, bar_width), 0)
            gradient.setColorAt(0.0, QColor("#155F8E"))
            gradient.setColorAt(1.0, QColor("#55A8C7"))
            painter.setBrush(gradient)
            painter.drawRoundedRect(
                QRectF(left, center_y - bar_height / 2, max(3.0, bar_width), bar_height),
                bar_height / 2,
                bar_height / 2,
            )

            painter.setFont(value_font)
            painter.setPen(fill.darker(120))
            painter.drawText(
                QRectF(left + width + 8, y, right - 12, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                f"₡{value / 1_000_000:,.0f} MM",
            )


class _LiquidityWaterfallChart(QWidget):
    """Executive waterfall for 30-day liquidity bridge."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: tuple[tuple[str, float], ...] = ()
        self.setMinimumHeight(250)

    def set_data(self, points: tuple[tuple[str, float], ...]) -> None:
        self._points = points
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        if len(self._points) < 4:
            painter.setPen(QColor("#718096"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles")
            return

        values = [float(value) for _, value in self._points]
        bridge = (
            ("Fondo líquido", values[0], "total"),
            ("Entradas 30d", values[1], "positive"),
            ("Salidas 30d", -abs(values[2]), "negative"),
            ("Salida neta", -abs(values[3]), "negative"),
        )

        left, right, top, bottom = 48.0, 18.0, 26.0, 54.0
        width = max(60.0, self.width() - left - right)
        height = max(60.0, self.height() - top - bottom)
        slot = width / len(bridge)
        running = bridge[0][1]
        levels = [0.0, running]
        for _, value, _ in bridge[1:]:
            running += value
            levels.append(running)
        minimum = min(0.0, *levels)
        maximum = max(*levels)
        span = max(maximum - minimum, 1.0)

        def y_coord(value: float) -> float:
            return top + height - (value - minimum) / span * height

        for index in range(5):
            y = top + height * index / 4
            painter.setPen(QPen(QColor("#EEF2F5"), 1))
            painter.drawLine(QPointF(left, y), QPointF(left + width, y))

        baseline_y = y_coord(0.0)
        painter.setPen(QPen(QColor("#C9D4DD"), 1.2))
        painter.drawLine(QPointF(left, baseline_y), QPointF(left + width, baseline_y))

        running = 0.0
        previous_end = 0.0
        previous_center = None
        for index, (label, value, kind) in enumerate(bridge):
            center = left + slot * index + slot / 2
            bar_width = min(72.0, slot * 0.50)

            if index == 0:
                start_level = 0.0
                end_level = value
                running = value
            else:
                start_level = running
                end_level = running + value
                running = end_level

            top_value = max(start_level, end_level)
            bottom_value = min(start_level, end_level)
            rect_top = y_coord(top_value)
            rect_bottom = y_coord(bottom_value)
            rect_height = max(3.0, rect_bottom - rect_top)

            if previous_center is not None:
                connector_y = y_coord(previous_end)
                painter.setPen(QPen(QColor("#AFC0CC"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(
                    QPointF(previous_center + bar_width / 2, connector_y),
                    QPointF(center - bar_width / 2, connector_y),
                )

            fill = (
                QColor("#1C8A63")
                if kind == "positive"
                else QColor("#C84A3A") if kind == "negative" else QColor("#1F6F9F")
            )
            gradient = QLinearGradient(0, rect_top, 0, rect_top + rect_height)
            gradient.setColorAt(0.0, fill.lighter(118))
            gradient.setColorAt(1.0, fill)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(
                QRectF(center - bar_width / 2, rect_top, bar_width, rect_height),
                6,
                6,
            )

            font = QFont(self.font())
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(QColor("#23384B"))
            painter.drawText(
                QRectF(center - slot / 2, top + height + 8, slot, 20),
                Qt.AlignmentFlag.AlignHCenter,
                label,
            )
            painter.setPen(fill.darker(118))
            prefix = "+" if kind == "positive" else "−" if kind == "negative" else ""
            painter.drawText(
                QRectF(center - slot / 2, max(2.0, rect_top - 22), slot, 20),
                Qt.AlignmentFlag.AlignHCenter,
                f"{prefix}₡{abs(value) / 1_000_000:,.0f} MM",
            )
            previous_end = end_level
            previous_center = center


class LiquidityView(QWidget):
    """Panel institucional de liquidez para ICL, HQLA, MIL y flujos contractuales."""

    _DISPLAY_TRANSLATIONS = {
        "READY": "LISTO",
        "LOADED": "CARGADO",
        "AVAILABLE": "DISPONIBLE",
        "UNAVAILABLE": "NO DISPONIBLE",
        "ELIGIBLE": "ELEGIBLE",
        "NOT ELIGIBLE": "NO ELEGIBLE",
        "INELIGIBLE": "NO ELEGIBLE",
        "PASS": "CUMPLE",
        "FAIL": "NO CUMPLE",
        "NOT CONFIGURED": "NO CONFIGURADO",
        "NOT_CONFIGURED": "NO CONFIGURADO",
        "COUPON": "CUPÓN",
        "PRINCIPAL": "PRINCIPAL",
        "CONTRACTUAL": "CONTRACTUAL",
        "PROJECTED_CURRENT_RATE": "PROYECTADO TASA VIGENTE",
        "FX_UNAVAILABLE": "TC NO DISPONIBLE",
    }

    def __init__(self, presenter: LiquidityPresenter | None = None) -> None:
        super().__init__()
        self.setObjectName("liquidityWorkspace")
        self._presenter = presenter or LiquidityPresenter()
        self._view_model = self._presenter.build_view_model()
        self._kpis: dict[str, QLabel] = {}
        self._build_ui()
        self.bind_view_model(self._view_model)

    @classmethod
    def _translate(cls, value: object) -> str:
        text = str(value)
        return cls._DISPLAY_TRANSLATIONS.get(text.strip().upper(), text)

    @staticmethod
    def _format_crc_mm(value: float) -> str:
        return f"₡{value / 1_000_000:,.2f} MM"

    @staticmethod
    def _format_local(value: float, currency: str) -> str:
        return f"{currency} {value:,.2f}"

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D7E0E8; border-radius:8px; margin-top:8px; "
            "font-weight:700; color:#22384C; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )

    def _metric_card(self, key: str, title: str, helper: str) -> QFrame:
        card = QFrame()
        card.setObjectName("liquidityMetricCard")
        card.setMinimumHeight(76)
        accent = {
            "icl_total": ("#005EB8", "#EAF5FB"),
            "icl_mn": ("#00A9E0", "#EDF9FD"),
            "icl_me": ("#40C1AC", "#EAF7F2"),
            "liquid_fund": ("#005EB8", "#F0F8FC"),
            "hqla": ("#40C1AC", "#ECF8F4"),
            "mil": ("#00A9E0", "#EDF8FC"),
            "maturity30": ("#FF8200", "#FFF5E9"),
            "coupon30": ("#2B9E8B", "#ECF8F4"),
        }.get(key, ("#00A9E0", "#F7FBFD"))
        card.setStyleSheet(
            "QFrame#liquidityMetricCard {"
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #FFFFFF,stop:1 {accent[1]}); "
            f"border:1px solid #D0DEE7; border-left:4px solid {accent[0]}; border-radius:10px;"
            "} QFrame#liquidityMetricCard:hover {border-color:#73B3DD;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        caption = QLabel(title)
        caption.setStyleSheet("color:#667788; font-size:9px; border:none;")
        value = QLabel("-")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        value.setFont(font)
        value.setStyleSheet("color:#142E46; border:none;")
        hint = QLabel(helper)
        hint.setStyleSheet("color:#8A98A6; font-size:8px; border:none;")
        layout.addWidget(caption)
        layout.addWidget(value)
        layout.addWidget(hint)
        self._kpis[key] = value
        return card

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("GESTIÓN DE LIQUIDEZ")
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        title.setFont(font)
        subtitle = QLabel("UX V3 · ICL · HQLA · MIL · cupones y principal · capacidad de respuesta")
        subtitle.setStyleSheet("color:#667788; font-size:10px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self._date_label = QLabel("-")
        self._date_label.setStyleSheet(
            "padding:7px 11px; background:#F3F6F9; border:1px solid #D7E0E8; "
            "border-radius:6px; font-weight:600;"
        )
        header.addWidget(self._date_label)
        root.addLayout(header)

        kpis = QGridLayout()
        kpis.setHorizontalSpacing(7)
        definitions = (
            ("icl_total", "ICL Total", "Indicador institucional"),
            ("icl_mn", "ICL MN", "Moneda nacional"),
            ("icl_me", "ICL ME", "Moneda extranjera"),
            ("liquid_fund", "Fondo líquido", "Activos líquidos ICL"),
            ("hqla", "HQLA", "Capacidad ajustada elegible"),
            ("mil", "MIL", "Capacidad de garantía elegible"),
            ("maturity30", "Principal ≤30 días", "Flujo contractual de inversiones"),
            ("coupon30", "Cupones ≤30 días", "Ingreso contractual/proyectado"),
        )
        for index, definition in enumerate(definitions):
            kpis.addWidget(self._metric_card(*definition), index // 4, index % 4)
        root.addLayout(kpis)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabBar::tab {padding:8px 18px; font-weight:600;}"
            "QTabBar::tab:selected {color:#174E78; border-bottom:2px solid #1F5A8A;}"
        )
        root.addWidget(self._tabs, 1)
        self._build_summary_tab()
        self._cashflow_table = self._build_cashflow_tab()
        self._maturity_table = self._build_maturity_tab()
        self._hqla_table = self._build_eligibility_tab("HQLA")
        self._mil_table = self._build_eligibility_tab("MIL")
        self._build_stress_tab()

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color:#617386; padding:3px 2px;")
        root.addWidget(self._status)

    def _build_summary_tab(self) -> None:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(8)

        flow_group = QGroupBox("Puente de liquidez · 30 días")
        flow_group.setStyleSheet(self._group_style())
        flow_layout = QVBoxLayout(flow_group)
        self._flow_chart = _LiquidityWaterfallChart()
        flow_layout.addWidget(self._flow_chart)
        layout.addWidget(flow_group, 1)

        maturity_group = QGroupBox("Flujos contractuales acumulados del portafolio")
        maturity_group.setStyleSheet(self._group_style())
        maturity_layout = QVBoxLayout(maturity_group)
        self._maturity_chart = _LiquidityBarChart()
        maturity_layout.addWidget(self._maturity_chart)
        layout.addWidget(maturity_group, 1)
        self._tabs.addTab(page, "Resumen ejecutivo")

    def _new_table(self, headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(list(headers))
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(26)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        return table

    def _build_cashflow_tab(self) -> QTableWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        table = self._new_table(
            (
                "Tipo",
                "Serie",
                "Emisor",
                "Moneda",
                "Fecha flujo",
                "Días",
                "Tramo",
                "Monto local",
                "Monto CRC",
                "Estado",
                "Fuente",
            )
        )
        layout.addWidget(table)
        self._tabs.addTab(page, "Flujos Portafolio")
        return table

    def _build_maturity_tab(self) -> QTableWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        table = self._new_table(
            (
                "Serie",
                "Emisor",
                "Moneda",
                "Clasificación",
                "Vencimiento",
                "Días",
                "Tramo",
                "Principal contractual CRC",
            )
        )
        layout.addWidget(table)
        self._tabs.addTab(page, "Vencimientos")
        return table

    def _build_eligibility_tab(self, label: str) -> QTableWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        table = self._new_table(
            (
                "Serie",
                "Emisor",
                "Moneda",
                "Clasificación",
                "Valor de Mercado",
                "Factor",
                "Capacidad",
                "Estado",
                "Referencia",
            )
        )
        layout.addWidget(table)
        self._tabs.addTab(page, label)
        return table

    def _build_stress_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        group = QGroupBox("Estrés de liquidez")
        group.setStyleSheet(self._group_style())
        group_layout = QVBoxLayout(group)
        self._stress_status = QLabel("-")
        stress_font = QFont()
        stress_font.setPointSize(16)
        stress_font.setBold(True)
        self._stress_status.setFont(stress_font)
        self._stress_status.setStyleSheet("color:#17324D; padding:10px;")
        self._policy_status = QLabel("-")
        self._policy_status.setStyleSheet("color:#667788; padding:0 10px 10px 10px;")
        notice = QLabel(
            "El panel sólo muestra resultados de estrés calculados por el motor institucional. "
            "No se generan escenarios ni supuestos dentro de la interfaz."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet("color:#7A8794; padding:10px;")
        group_layout.addWidget(self._stress_status)
        group_layout.addWidget(self._policy_status)
        group_layout.addWidget(notice)
        layout.addWidget(group)
        layout.addStretch(1)
        self._tabs.addTab(page, "Estrés")

    @staticmethod
    def _set_item(table: QTableWidget, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        if column >= 4:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table.setItem(row, column, item)

    def _populate_cashflows(self, rows: tuple[LiquidityRow, ...]) -> None:
        table = self._cashflow_table
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            crc_text = (
                self._format_crc_mm(row.amount_crc)
                if row.amount_crc is not None
                else "TC no disponible"
            )
            values = (
                self._translate(row.flow_type),
                row.label,
                row.issuer,
                row.currency,
                row.maturity_date,
                str(row.days_to_maturity if row.days_to_maturity is not None else "-"),
                self._translate(row.bucket),
                self._format_local(row.amount_local, row.currency),
                crc_text,
                self._translate(row.status),
                row.policy_reference,
            )
            for column, value in enumerate(values):
                self._set_item(table, row_index, column, value)
        table.setSortingEnabled(True)

    def _populate_maturities(self, rows: tuple[LiquidityRow, ...]) -> None:
        table = self._maturity_table
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row.label,
                row.issuer,
                row.currency,
                self._translate(row.classification),
                row.maturity_date,
                str(row.days_to_maturity if row.days_to_maturity is not None else "-"),
                self._translate(row.bucket),
                self._format_crc_mm(float(row.value)),
            )
            for column, value in enumerate(values):
                self._set_item(table, row_index, column, value)
        table.setSortingEnabled(True)

    def _populate_eligibility(
        self,
        table: QTableWidget,
        rows: tuple[LiquidityRow, ...],
    ) -> None:
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row.label,
                row.issuer,
                row.currency,
                self._translate(row.classification),
                self._format_crc_mm(row.market_value_crc),
                f"{row.factor:.2%}",
                self._format_crc_mm(float(row.value)),
                self._translate(row.status),
                row.policy_reference,
            )
            for column, value in enumerate(values):
                self._set_item(table, row_index, column, value)
        table.setSortingEnabled(True)

    def refresh(self) -> None:
        self.bind_view_model(self._presenter.refresh())

    def bind_view_model(self, view_model: LiquidityViewModel) -> None:
        self._view_model = view_model
        summary = view_model.summary
        self._date_label.setText(f"Corte: {getattr(summary, 'liquidity_date', '-')}")
        values = {
            "icl_total": f"{getattr(summary, 'icl_total', 0.0):.2f}",
            "icl_mn": f"{getattr(summary, 'icl_mn', 0.0):.2f}",
            "icl_me": f"{getattr(summary, 'icl_me', 0.0):.2f}",
            "liquid_fund": self._format_crc_mm(getattr(summary, "liquid_asset_fund_total", 0.0)),
            "hqla": self._format_crc_mm(getattr(summary, "hqla_capacity_value", 0.0)),
            "mil": self._format_crc_mm(getattr(summary, "mil_capacity_value", 0.0)),
            "maturity30": self._format_crc_mm(getattr(summary, "principal_inflows_30d_crc", 0.0)),
            "coupon30": self._format_crc_mm(getattr(summary, "coupon_inflows_30d_crc", 0.0)),
        }
        for key, value in values.items():
            self._kpis[key].setText(value)

        self._flow_chart.set_data(
            (
                ("Fondo líquido", getattr(summary, "liquid_asset_fund_total", 0.0)),
                ("Entradas 30 días", getattr(summary, "total_inflows_30d", 0.0)),
                ("Salidas 30 días", getattr(summary, "total_outflows_30d", 0.0)),
                ("Salida neta", getattr(summary, "net_cash_outflow_30d", 0.0)),
            )
        )
        self._maturity_chart.set_data(
            (
                ("Principal ≤30d", getattr(summary, "principal_inflows_30d_crc", 0.0)),
                ("Cupones ≤30d", getattr(summary, "coupon_inflows_30d_crc", 0.0)),
                ("Principal ≤90d", getattr(summary, "principal_inflows_90d_crc", 0.0)),
                ("Cupones ≤90d", getattr(summary, "coupon_inflows_90d_crc", 0.0)),
            )
        )
        self._populate_cashflows(view_model.cashflow_rows)
        self._populate_maturities(view_model.maturity_rows)
        self._populate_eligibility(self._hqla_table, view_model.hqla_rows)
        self._populate_eligibility(self._mil_table, view_model.mil_rows)
        self._stress_status.setText(
            f"Resultado: {self._translate(getattr(summary, 'stress_result', '-'))}"
        )
        self._policy_status.setText(
            f"Política: {self._translate(getattr(summary, 'policy_status', '-'))}"
        )
        message = getattr(summary, "configuration_message", "") or (
            view_model.error or view_model.status
        )
        self._status.setText(self._translate(message))

    def view_model(self) -> LiquidityViewModel:
        return self._view_model
