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
from aip.ui.modules.financial_analysis.views.financial_history_panel import (
    FinancialHistoryPanel,
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
        self._cutoff = QLabel("Corte SUGEF: -")
        self._cutoff.setToolTip(
            "Último corte oficial SUGEF disponible que no excede el corte general de AIP."
        )
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
            [
                "Entidad",
                "Categoría",
                "Activos",
                "Cartera",
                "Patrimonio",
                "Resultado",
                "ROA",
                "ROE",
            ]
        )
        self._history_panel = FinancialHistoryPanel()
        self._rating_panel = self._build_rating_panel()
        self._diagnostics = QListWidget()
        self._tabs.addTab(self._statement_table, "Estados financieros")
        self._tabs.addTab(self._peer_table, "Comparativo de entidades")
        self._tabs.addTab(self._history_panel, "KPIs históricos")
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
            "QTabWidget#ratingContentTabs::pane {border:1px solid #D7E0E8; "
            "border-radius:6px; background:#FFFFFF;}"
            "QLabel#ratingNotes {background:#FFF9E8; border:1px solid #E8D79E; "
            "border-radius:6px; color:#5D563E; padding:6px 9px;}"
        )

    def _build_rating_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        summary = QFrame()
        summary.setObjectName("ratingSummary")
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(14, 8, 14, 8)
        summary_layout.setHorizontalSpacing(22)
        self._rating_heading = QLabel("Calificación 08ME14-01 sobre datos SUGEF")
        self._rating_heading.setStyleSheet("font-size:11px; font-weight:600; color:#314A5E;")
        self._rating_grade = QLabel("Sin emitir")
        self._rating_grade.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rating_grade.setMinimumWidth(80)
        self._rating_grade.setStyleSheet("font-size:30px; font-weight:700; color:#005EB8;")
        self._rating_score = QLabel("Puntaje: -")
        self._rating_score.setStyleSheet("font-size:15px; font-weight:700; color:#142E46;")
        self._rating_coverage = QLabel("Cobertura: 0.00%")
        self._rating_coverage.setStyleSheet("font-size:11px; font-weight:600; color:#314A5E;")
        self._rating_methodology = QLabel("Metodología: 08ME14-01")
        self._rating_methodology.setStyleSheet("color:#52687A; font-size:10px;")
        summary_layout.addWidget(self._rating_grade, 0, 0, 2, 1)
        summary_layout.addWidget(self._rating_heading, 0, 1)
        summary_layout.addWidget(self._rating_score, 1, 1)
        summary_layout.addWidget(self._rating_coverage, 0, 2)
        summary_layout.addWidget(self._rating_methodology, 1, 2)
        summary_layout.setColumnStretch(1, 1)
        summary_layout.setColumnStretch(2, 1)
        layout.addWidget(summary)

        self._rating_content_tabs = QTabWidget()
        self._rating_content_tabs.setObjectName("ratingContentTabs")
        self._rating_content_tabs.setDocumentMode(True)

        ranking = QWidget()
        ranking_layout = QVBoxLayout(ranking)
        ranking_layout.setContentsMargins(8, 8, 8, 8)
        ranking_layout.setSpacing(6)
        ranking_header = QHBoxLayout()
        ranking_title_box = QVBoxLayout()
        ranking_title = QLabel("Calificación comparativa de entidades SUGEF")
        ranking_title.setStyleSheet("font-weight:700; color:#314A5E; font-size:11px;")
        ranking_help = QLabel(
            "Mismo corte, universo y metodología 08ME14-01. La nota solo se emite con los "
            "13 indicadores disponibles; doble clic abre el detalle de la entidad."
        )
        ranking_help.setStyleSheet("color:#667788; font-size:9px;")
        ranking_title_box.addWidget(ranking_title)
        ranking_title_box.addWidget(ranking_help)
        ranking_header.addLayout(ranking_title_box)
        ranking_header.addStretch(1)
        self._peer_rating_summary = QLabel("Sin calificaciones comparativas")
        self._peer_rating_summary.setStyleSheet("font-weight:600; color:#52687A; font-size:9px;")
        ranking_header.addWidget(self._peer_rating_summary)
        ranking_layout.addLayout(ranking_header)

        self._peer_rating_table = self._table(
            [
                "Pos.",
                "Entidad",
                "Categoría",
                "Puntaje",
                "Nota",
                "Cobertura",
                "Indicadores",
                "Estado",
            ]
        )
        peer_rating_header = self._peer_rating_table.horizontalHeader()
        peer_rating_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        peer_rating_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        peer_rating_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in range(3, 8):
            peer_rating_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._peer_rating_table.cellDoubleClicked.connect(self._rating_entity_activated)
        ranking_layout.addWidget(self._peer_rating_table, 1)
        self._rating_content_tabs.addTab(ranking, "Ranking de entidades")

        detail = QWidget()
        detail_layout = QHBoxLayout(detail)
        detail_layout.setContentsMargins(8, 8, 8, 8)
        detail_layout.setSpacing(10)

        self._rating_dimension_table = self._table(["Dimensión", "Puntaje", "Peso", "Cobertura"])
        self._rating_dimension_table.setMinimumWidth(390)
        self._rating_dimension_table.setMaximumWidth(455)
        self._rating_dimension_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        dimension_header = self._rating_dimension_table.horizontalHeader()
        dimension_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            dimension_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        self._rating_indicator_table = self._table(
            [
                "Indicador",
                "Dimensión",
                "Valor",
                "Pares",
                "P15",
                "Punto medio",
                "P85",
                "Dirección",
                "Nivel",
                "Aporte",
                "Cuenta fuente",
            ]
        )
        self._rating_indicator_table.setColumnHidden(10, True)
        indicator_header = self._rating_indicator_table.horizontalHeader()
        indicator_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 10):
            indicator_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        peer_header = self._rating_indicator_table.horizontalHeaderItem(3)
        if peer_header is not None:
            peer_header.setToolTip(
                "Cantidad de entidades con un valor comparable disponible para el indicador."
            )

        detail_layout.addWidget(self._rating_dimension_table, 2)
        detail_layout.addWidget(self._rating_indicator_table, 6)
        self._rating_content_tabs.addTab(detail, "Indicadores y dimensiones")

        reconciliation = QWidget()
        reconciliation_layout = QVBoxLayout(reconciliation)
        reconciliation_layout.setContentsMargins(8, 8, 8, 8)
        reconciliation_layout.setSpacing(6)
        reconciliation_title = QLabel("SUGEF publicado vs AIP calculado")
        reconciliation_title.setStyleSheet("font-weight:700; color:#314A5E; font-size:11px;")
        reconciliation_help = QLabel(
            "Contraste del valor publicado por SUGEF con el cálculo independiente de AIP. "
            "Las fuentes completas se muestran al posicionar el cursor sobre cada celda."
        )
        reconciliation_help.setStyleSheet("color:#667788; font-size:9px;")
        reconciliation_layout.addWidget(reconciliation_title)
        reconciliation_layout.addWidget(reconciliation_help)

        self._reconciliation_table = self._table(
            [
                "Indicador",
                "SUGEF publicado",
                "AIP calculado",
                "Diferencia",
                "Estado",
                "Fuente SUGEF",
                "Fuente cálculo",
            ]
        )
        reconciliation_header = self._reconciliation_table.horizontalHeader()
        reconciliation_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            reconciliation_header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        reconciliation_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        reconciliation_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        reconciliation_layout.addWidget(self._reconciliation_table, 1)
        self._rating_content_tabs.addTab(reconciliation, "Reconciliación")

        layout.addWidget(self._rating_content_tabs, 1)

        self._rating_notes = QLabel()
        self._rating_notes.setObjectName("ratingNotes")
        self._rating_notes.setWordWrap(True)
        self._rating_notes.setMaximumHeight(54)
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
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(28)
        table.horizontalHeader().setMinimumSectionSize(52)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def bind_view_model(self, view_model: FinancialAnalysisViewModel) -> None:
        self._view_model = view_model
        self._title.setText(view_model.title)
        self._subtitle.setText(view_model.subtitle)
        self._cutoff.setText(f"Corte SUGEF: {view_model.cutoff_date}")
        self._bind_entities(view_model)
        metrics = {item.code: item for item in view_model.metrics}
        for code in self._KPI_ORDER:
            metric = metrics.get(code)
            self._kpi_values[code].setText(metric.value if metric else "-")
            self._kpi_changes[code].setText(metric.change if metric else "Sin datos")
            self._kpi_values[code].setToolTip(metric.source_account if metric else "")
        self._bind_statements(view_model)
        self._bind_peers(view_model)
        self._history_panel.bind_history(view_model.metric_history)
        self._bind_rating(view_model)
        self._diagnostics.clear()
        self._diagnostics.addItems(list(view_model.diagnostics) or ["Sin incidencias de calidad."])
        status = {
            "AVAILABLE": "Estados completos",
            "PARTIAL": "Cobertura parcial",
        }.get(view_model.status, "Pendiente de datos")
        self._source_status.setText(
            f"{view_model.source_name} · {status} · {view_model.source_file_count} fuente(s) procesada(s)"
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
        self._bind_peer_ratings(view_model)
        self._rating_grade.setText(view_model.rating_grade)
        self._rating_score.setText(f"Puntaje: {view_model.rating_score}")
        self._rating_coverage.setText(f"Cobertura: {view_model.rating_coverage}")
        self._rating_methodology.setText(f"Metodología: {view_model.rating_methodology}")
        self._rating_grade.setStyleSheet(
            "font-size:30px; font-weight:700; color:#138A62;"
            if view_model.rating_status == "COMPLETE"
            else "font-size:30px; font-weight:700; color:#A66A00;"
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
                row.peer_count,
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
                if column in {2, 3, 4, 5, 6, 9}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if row.source_account:
                    item.setToolTip(f"Cuenta/fuente: {row.source_account}")
                self._rating_indicator_table.setItem(row_index, column, item)

        self._reconciliation_table.setRowCount(len(view_model.indicator_reconciliations))
        for row_index, row in enumerate(view_model.indicator_reconciliations):
            reconciliation_values = (
                row.indicator,
                row.published_value,
                row.calculated_value,
                row.difference,
                row.status,
                row.published_source,
                row.calculated_source,
            )
            for column, value in enumerate(reconciliation_values):
                item = QTableWidgetItem(value)
                if column in {1, 2, 3}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if column == 5 and row.published_source:
                    item.setToolTip(row.published_source)
                elif column == 6 and row.calculated_source:
                    item.setToolTip(row.calculated_source)
                self._reconciliation_table.setItem(row_index, column, item)

        notes = list(view_model.rating_diagnostics) or [
            "P15/P85, ponderaciones y escala aplicadas conforme a 08ME14-01 V01.",
            "Fuente de indicadores: SUGEF; los faltantes permanecen no disponibles o se calculan desde estados financieros SUGEF cuando la metodología lo permite.",
        ]
        notes_text = "  •  ".join(notes)
        self._rating_notes.setText(notes_text)
        self._rating_notes.setToolTip("\n".join(notes))

    def _bind_peer_ratings(self, view_model: FinancialAnalysisViewModel) -> None:
        rows = view_model.peer_rating_rows
        complete_count = sum(row.status == "Emitida" for row in rows)
        self._peer_rating_summary.setText(
            f"{complete_count} emitidas · {len(rows)} entidades"
            if rows
            else "Sin calificaciones comparativas"
        )
        self._peer_rating_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row.position,
                row.entity_name,
                row.category,
                row.score,
                row.grade,
                row.coverage,
                row.indicators,
                row.status,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row.entity_id)
                if column in {0, 3, 5, 6}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                elif column in {4, 7}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if row.selected:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setToolTip("Entidad seleccionada · doble clic para abrir el detalle")
                else:
                    item.setToolTip("Doble clic para abrir el detalle de la entidad")
                self._peer_rating_table.setItem(row_index, column, item)

    def _rating_entity_activated(self, row: int, _column: int) -> None:
        item = self._peer_rating_table.item(row, 0)
        if item is None:
            return
        entity_id = item.data(Qt.ItemDataRole.UserRole)
        if not entity_id:
            return
        selected = self._entity_selector.findData(str(entity_id))
        if selected >= 0:
            self._entity_selector.setCurrentIndex(selected)

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
