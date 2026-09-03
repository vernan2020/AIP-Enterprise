from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
    FinancialAnalysisPresenter,
)
from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
)


class FinancialAnalysisView(QWidget):
    """Workspace comparativo de estados financieros publicados por SUGEF."""

    _KPI_ORDER = ("ASSETS", "LOANS", "LIABILITIES", "EQUITY", "NET_INCOME", "ROA", "ROE")

    def __init__(self, presenter: FinancialAnalysisPresenter | None = None) -> None:
        super().__init__()
        self.setObjectName("financialAnalysisWorkspace")
        self._presenter = presenter or FinancialAnalysisPresenter()
        self._view_model = FinancialAnalysisViewModel()
        self._kpi_values: dict[str, QLabel] = {}
        self._kpi_changes: dict[str, QLabel] = {}
        self._building_entity_selector = False
        self._build_ui()
        self.bind_view_model(self._presenter.build_view_model())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self._title = QLabel("ANÁLISIS FINANCIERO")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self._title.setFont(title_font)
        self._subtitle = QLabel(
            "Estados financieros y comparación de entidades supervisadas por SUGEF"
        )
        self._subtitle.setStyleSheet("color:#667788; font-size:10px;")
        title_box.addWidget(self._title)
        title_box.addWidget(self._subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(QLabel("Entidad:"))
        self._entity_selector = QComboBox()
        self._entity_selector.setMinimumWidth(310)
        self._entity_selector.currentIndexChanged.connect(self._entity_changed)
        header.addWidget(self._entity_selector)
        self._refresh_button = QPushButton("Actualizar fuente")
        self._refresh_button.clicked.connect(self._refresh)
        header.addWidget(self._refresh_button)
        self._cutoff = QLabel("Corte: -")
        self._cutoff.setStyleSheet(
            "padding:7px 11px; background:#F3F6F9; border:1px solid #D7E0E8; "
            "border-radius:6px; font-weight:600;"
        )
        header.addWidget(self._cutoff)
        root.addLayout(header)

        kpis = QGridLayout()
        kpis.setHorizontalSpacing(7)
        for index, definition in enumerate(
            (
                ("ASSETS", "Activos"),
                ("LOANS", "Cartera de crédito"),
                ("LIABILITIES", "Pasivos"),
                ("EQUITY", "Patrimonio"),
                ("NET_INCOME", "Resultado neto"),
                ("ROA", "ROA"),
                ("ROE", "ROE"),
            )
        ):
            kpis.addWidget(self._metric_card(*definition), 0, index)
        root.addLayout(kpis)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._statement_table = self._table(
            ["Estado", "Cuenta", "Descripción", "Valor", "Moneda", "Trazabilidad"]
        )
        self._peer_table = self._table(
            ["Entidad", "Categoría", "Activos", "Cartera", "Patrimonio", "Resultado", "ROA", "ROE"]
        )
        self._rating_panel = self._build_rating_panel()
        self._diagnostics = QListWidget()
        self._tabs.addTab(self._statement_table, "Estados financieros")
        self._tabs.addTab(self._peer_table, "Comparativo de entidades")
        self._tabs.addTab(self._rating_panel, "Calificación")
        self._tabs.addTab(self._diagnostics, "Calidad y trazabilidad")
        root.addWidget(self._tabs, 1)

        source = QFrame()
        source.setObjectName("sugefSourcePanel")
        source_layout = QHBoxLayout(source)
        source_layout.setContentsMargins(10, 6, 10, 6)
        self._source_status = QLabel("SUGEF · fuente no configurada")
        source_layout.addWidget(self._source_status)
        source_layout.addStretch(1)
        self._source_link = QPushButton("Abrir fuente oficial")
        self._source_link.clicked.connect(self._open_source)
        source_layout.addWidget(self._source_link)
        root.addWidget(source)

        self.setStyleSheet(
            "QFrame#financialMetricCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:8px;} QFrame#sugefSourcePanel {background:#F3F8FB; "
            "border:1px solid #CFE0EC; border-radius:7px;}"
            "QComboBox, QPushButton {padding:6px 8px;}"
            "QTabBar::tab {padding:8px 18px; font-weight:600;}"
            "QTabBar::tab:selected {color:#005EB8; border-bottom:2px solid #00A9E0;}"
            "QFrame#ratingSummary {background:#F3F8FB; border:1px solid #CFE0EC; "
            "border-radius:8px;}"
        )

    def _build_rating_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        summary = QFrame()
        summary.setObjectName("ratingSummary")
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        self._rating_grade = QLabel("Sin emitir")
        self._rating_grade.setStyleSheet("font-size:22px; font-weight:700; color:#005EB8;")
        self._rating_score = QLabel("Puntaje: -")
        self._rating_score.setStyleSheet("font-size:14px; font-weight:600;")
        self._rating_coverage = QLabel("Cobertura: 0.00%")
        self._rating_methodology = QLabel("Metodología: 08ME14-01")
        self._rating_methodology.setStyleSheet("color:#52687A;")
        summary_layout.addWidget(QLabel("Calificación oficial"), 0, 0)
        summary_layout.addWidget(self._rating_grade, 1, 0)
        summary_layout.addWidget(self._rating_score, 0, 1)
        summary_layout.addWidget(self._rating_coverage, 1, 1)
        summary_layout.addWidget(self._rating_methodology, 0, 2, 2, 1)
        summary_layout.setColumnStretch(2, 1)
        layout.addWidget(summary)

        tables = QHBoxLayout()
        self._rating_dimension_table = self._table(["Dimensión", "Puntaje", "Peso", "Cobertura"])
        self._rating_dimension_table.setMinimumWidth(390)
        self._rating_indicator_table = self._table(
            [
                "Indicador",
                "Dimensión",
                "Valor",
                "P15",
                "Punto medio",
                "P85",
                "Dirección",
                "Nivel",
                "Aporte",
                "Cuenta fuente",
            ]
        )
        tables.addWidget(self._rating_dimension_table, 2)
        tables.addWidget(self._rating_indicator_table, 5)
        layout.addLayout(tables, 1)

        self._rating_notes = QListWidget()
        self._rating_notes.setMaximumHeight(76)
        layout.addWidget(self._rating_notes)
        return panel

    def _metric_card(self, code: str, label: str) -> QFrame:
        card = QFrame()
        card.setObjectName("financialMetricCard")
        card.setMinimumHeight(82)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(9, 7, 9, 7)
        caption = QLabel(label)
        caption.setStyleSheet("color:#667788; font-size:8px; border:none;")
        value = QLabel("-")
        value.setStyleSheet("color:#142E46; font-size:12px; font-weight:700; border:none;")
        change = QLabel("Sin datos")
        change.setStyleSheet("color:#8393A3; font-size:7px; border:none;")
        change.setWordWrap(True)
        layout.addWidget(caption)
        layout.addWidget(value)
        layout.addWidget(change)
        self._kpi_values[code] = value
        self._kpi_changes[code] = change
        return card

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

    def bind_view_model(self, view_model: FinancialAnalysisViewModel) -> None:
        self._view_model = view_model
        self._title.setText(view_model.title)
        self._subtitle.setText(view_model.subtitle)
        self._cutoff.setText(f"Corte: {view_model.cutoff_date}")
        self._bind_entities(view_model)
        metrics = {item.code: item for item in view_model.metrics}
        for code in self._KPI_ORDER:
            metric = metrics.get(code)
            self._kpi_values[code].setText(metric.value if metric else "-")
            self._kpi_changes[code].setText(metric.change if metric else "Sin datos")
            self._kpi_values[code].setToolTip(metric.source_account if metric else "")
        self._bind_statements(view_model)
        self._bind_peers(view_model)
        self._bind_rating(view_model)
        self._diagnostics.clear()
        self._diagnostics.addItems(list(view_model.diagnostics) or ["Sin incidencias de calidad."])
        status = {
            "AVAILABLE": "Estados completos",
            "PARTIAL": "Cobertura parcial",
        }.get(view_model.status, "Pendiente de datos")
        self._source_status.setText(
            f"{view_model.source_name} · {status} · {view_model.source_file_count} archivo(s) procesado(s)"
        )

    def _bind_entities(self, view_model: FinancialAnalysisViewModel) -> None:
        self._building_entity_selector = True
        try:
            self._entity_selector.clear()
            for entity_id, name in view_model.entities:
                self._entity_selector.addItem(name, entity_id)
            selected = self._entity_selector.findData(view_model.selected_entity_id)
            if selected >= 0:
                self._entity_selector.setCurrentIndex(selected)
        finally:
            self._building_entity_selector = False

    def _bind_statements(self, view_model: FinancialAnalysisViewModel) -> None:
        self._statement_table.setRowCount(len(view_model.statement_rows))
        for row_index, row in enumerate(view_model.statement_rows):
            values = (
                row.statement,
                row.account_code,
                row.account_name,
                row.amount,
                row.currency,
                row.trace,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._statement_table.setItem(row_index, column, item)

    def _bind_peers(self, view_model: FinancialAnalysisViewModel) -> None:
        self._peer_table.setRowCount(len(view_model.peer_rows))
        for row_index, row in enumerate(view_model.peer_rows):
            values = (
                row.entity_name,
                row.category,
                row.assets,
                row.loans,
                row.equity,
                row.net_income,
                row.roa,
                row.roe,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column >= 2:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._peer_table.setItem(row_index, column, item)

    def _bind_rating(self, view_model: FinancialAnalysisViewModel) -> None:
        self._rating_grade.setText(view_model.rating_grade)
        self._rating_score.setText(f"Puntaje: {view_model.rating_score}")
        self._rating_coverage.setText(f"Cobertura: {view_model.rating_coverage}")
        self._rating_methodology.setText(f"Metodología: {view_model.rating_methodology}")
        self._rating_grade.setStyleSheet(
            "font-size:22px; font-weight:700; color:#138A62;"
            if view_model.rating_status == "COMPLETE"
            else "font-size:22px; font-weight:700; color:#A66A00;"
        )

        self._rating_dimension_table.setRowCount(len(view_model.rating_dimensions))
        for row_index, row in enumerate(view_model.rating_dimensions):
            dimension_values = (row.name, row.score, row.weight, row.coverage)
            for column, value in enumerate(dimension_values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._rating_dimension_table.setItem(row_index, column, item)

        self._rating_indicator_table.setRowCount(len(view_model.rating_indicators))
        for row_index, row in enumerate(view_model.rating_indicators):
            indicator_values = (
                row.indicator,
                row.dimension,
                row.value,
                row.percentile_15,
                row.midpoint,
                row.percentile_85,
                row.direction,
                row.level,
                row.contribution,
                row.source_account,
            )
            for column, value in enumerate(indicator_values):
                item = QTableWidgetItem(value)
                if column in {2, 3, 4, 5, 8}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._rating_indicator_table.setItem(row_index, column, item)

        self._rating_notes.clear()
        self._rating_notes.addItems(
            list(view_model.rating_diagnostics)
            or [
                "P15/P85, ponderaciones y escala aplicadas conforme a 08ME14-01 V01.",
                "El Excel de julio 2026 se conserva como referencia histórica, no como política.",
            ]
        )

    def _entity_changed(self, _index: int) -> None:
        if self._building_entity_selector:
            return
        entity_id = self._entity_selector.currentData()
        if entity_id:
            self.bind_view_model(
                self._presenter.build_view_model(selected_entity_id=str(entity_id))
            )

    def _refresh(self) -> None:
        entity_id = self._entity_selector.currentData()
        self.bind_view_model(
            self._presenter.build_view_model(
                selected_entity_id=str(entity_id) if entity_id else None,
                force_refresh=True,
            )
        )

    def _open_source(self) -> None:
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(self._view_model.source_url))

    def view_model(self) -> FinancialAnalysisViewModel:
        return self._view_model
