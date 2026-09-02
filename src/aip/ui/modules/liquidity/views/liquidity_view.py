from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
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
    """Gráfico de barras nativo para valores calculados por la capa de aplicación."""

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

        left, right, top, bottom = 32.0, 20.0, 20.0, 52.0
        width = max(40.0, self.width() - left - right)
        height = max(40.0, self.height() - top - bottom)
        maximum = max((abs(value) for _, value in self._points), default=0.0) or 1.0
        slot = width / max(1, len(self._points))
        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)

        for index, (label, value) in enumerate(self._points):
            center = left + slot * index + slot / 2
            bar_width = min(54.0, slot * 0.55)
            bar_height = height * abs(value) / maximum
            rect = QRectF(center - bar_width / 2, top + height - bar_height, bar_width, bar_height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2B6F9F") if value >= 0 else QColor("#B55A4A"))
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QColor("#23384B"))
            painter.drawText(
                QRectF(center - slot / 2, top + height + 7, slot, 18),
                Qt.AlignmentFlag.AlignHCenter,
                label,
            )
            painter.setPen(QColor("#53697C"))
            painter.drawText(
                QRectF(center - slot / 2, max(0.0, rect.top() - 22), slot, 20),
                Qt.AlignmentFlag.AlignHCenter,
                f"₡{value / 1_000_000:,.0f} MM",
            )


class LiquidityView(QWidget):
    """Panel institucional de liquidez para ICL, HQLA, MIL y vencimientos."""

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
        card.setStyleSheet(
            "QFrame#liquidityMetricCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:8px;} QFrame#liquidityMetricCard:hover {border-color:#8DB0CB;}"
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
        subtitle = QLabel("ICL · HQLA · MIL · vencimientos del portafolio · capacidad de respuesta")
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
            ("maturity30", "Vence ≤30 días", "Valor de mercado contractual"),
            ("net_outflow", "Salida neta 30 días", "Dato fuente ICL"),
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

        flow_group = QGroupBox("ICL · fondos y flujos a 30 días")
        flow_group.setStyleSheet(self._group_style())
        flow_layout = QVBoxLayout(flow_group)
        self._flow_chart = _LiquidityBarChart()
        flow_layout.addWidget(self._flow_chart)
        layout.addWidget(flow_group, 1)

        maturity_group = QGroupBox("Vencimientos acumulados del portafolio")
        maturity_group.setStyleSheet(self._group_style())
        maturity_layout = QVBoxLayout(maturity_group)
        self._maturity_chart = _LiquidityBarChart()
        maturity_layout.addWidget(self._maturity_chart)
        layout.addWidget(maturity_group, 1)
        self._tabs.addTab(page, "Resumen")

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
                "Valor de Mercado",
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
                self._format_crc_mm(row.market_value_crc),
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
            "maturity30": self._format_crc_mm(getattr(summary, "maturity_30d_crc", 0.0)),
            "net_outflow": self._format_crc_mm(getattr(summary, "net_cash_outflow_30d", 0.0)),
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
                ("≤30 días", getattr(summary, "maturity_30d_crc", 0.0)),
                ("≤90 días", getattr(summary, "maturity_90d_crc", 0.0)),
                ("≤180 días", getattr(summary, "maturity_180d_crc", 0.0)),
                ("≤270 días", getattr(summary, "maturity_270d_crc", 0.0)),
            )
        )
        self._populate_maturities(view_model.maturity_rows)
        self._populate_eligibility(self._hqla_table, view_model.hqla_rows)
        self._populate_eligibility(self._mil_table, view_model.mil_rows)
        self._stress_status.setText(
            f"Resultado: {self._translate(getattr(summary, 'stress_result', '-'))}"
        )
        self._policy_status.setText(
            f"Política: {self._translate(getattr(summary, 'policy_status', '-'))}"
        )
        message = getattr(summary, "configuration_message", "") or (view_model.error or view_model.status)
        self._status.setText(self._translate(message))

    def view_model(self) -> LiquidityViewModel:
        return self._view_model
