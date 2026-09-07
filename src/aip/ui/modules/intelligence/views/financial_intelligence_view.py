from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.intelligence.presenters.financial_intelligence_presenter import (
    FinancialIntelligencePresenter,
)
from aip.ui.modules.intelligence.viewmodels.financial_intelligence_view_model import (
    FinancialIntelligenceViewModel,
)


class _AnalysisWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, presenter: FinancialIntelligencePresenter, *, force_refresh: bool) -> None:
        super().__init__()
        self._presenter = presenter
        self._force_refresh = force_refresh

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(self._presenter.build_view_model(force_refresh=self._force_refresh))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class FinancialIntelligenceView(QWidget):
    """Financial Copilot workspace with deterministic evidence-grounded analysis."""

    def __init__(self, presenter: FinancialIntelligencePresenter) -> None:
        super().__init__()
        self._presenter = presenter
        self._thread: QThread | None = None
        self._worker: _AnalysisWorker | None = None
        self._model: FinancialIntelligenceViewModel | None = None
        self._loaded = False
        self._load_requested = False
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("AGENTE IA · FINANCIAL COPILOT")
        title.setObjectName("intelligenceTitle")
        subtitle = QLabel(
            "Alertas, diagnóstico y estrategias fundamentadas en los cálculos certificados de AIP."
        )
        subtitle.setObjectName("intelligenceSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_row.addLayout(title_box, 1)

        self._refresh_button = QPushButton("Actualizar análisis")
        self._refresh_button.clicked.connect(lambda: self._start_analysis(force_refresh=True))
        title_row.addWidget(self._refresh_button)
        root.addLayout(title_row)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(8)
        metrics.setVerticalSpacing(8)
        self._cutoff_card = self._metric_card("Corte", "–")
        self._mode_card = self._metric_card("Modo", "Pendiente")
        self._alerts_card = self._metric_card("Alertas", "–")
        self._opportunities_card = self._metric_card("Oportunidades", "–")
        self._coverage_card = self._metric_card("Cobertura", "–")
        self._provider_card = self._metric_card("LLM", "No configurado")
        cards = (
            self._cutoff_card,
            self._mode_card,
            self._alerts_card,
            self._opportunities_card,
            self._coverage_card,
            self._provider_card,
        )
        for index, card in enumerate(cards):
            metrics.addWidget(card, index // 3, index % 3)
        root.addLayout(metrics)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        findings_box = QGroupBox("Alertas y oportunidades")
        findings_layout = QVBoxLayout(findings_box)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(("Nivel", "Dominio", "Hallazgo", "Evidencia"))
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._show_selected_finding)
        findings_layout.addWidget(self._table)
        splitter.addWidget(findings_box)

        analysis_box = QGroupBox("Análisis ejecutivo")
        analysis_layout = QVBoxLayout(analysis_box)
        self._analysis_text = QTextEdit()
        self._analysis_text.setReadOnly(True)
        self._analysis_text.setPlaceholderText(
            "Abra esta pestaña para calcular el análisis financiero."
        )
        analysis_layout.addWidget(self._analysis_text, 1)

        question_row = QHBoxLayout()
        self._question = QLineEdit()
        self._question.setPlaceholderText(
            "Ej.: ¿Qué estrategia debería priorizar? / ¿Qué riesgos tiene el portafolio?"
        )
        self._question.returnPressed.connect(self._ask)
        self._ask_button = QPushButton("Preguntar")
        self._ask_button.setEnabled(False)
        self._ask_button.clicked.connect(self._ask)
        question_row.addWidget(self._question, 1)
        question_row.addWidget(self._ask_button)
        analysis_layout.addLayout(question_row)

        quick_row = QHBoxLayout()
        for label, question in (
            ("Prioridades", "¿Cuáles son las principales alertas y prioridades?"),
            ("Estrategias", "¿Qué estrategias recomienda AIP?"),
            ("Liquidez", "¿Qué debo vigilar en liquidez y HQLA?"),
            ("Portafolio", "¿Qué debo vigilar en duración y concentración del portafolio?"),
        ):
            button = QPushButton(label)
            button.setProperty("secondary", True)
            button.clicked.connect(lambda _checked=False, q=question: self._ask_text(q))
            quick_row.addWidget(button)
        analysis_layout.addLayout(quick_row)
        splitter.addWidget(analysis_box)
        splitter.setSizes([760, 760])
        root.addWidget(splitter, 1)

        self._status = QLabel(
            "Human-in-the-loop: el agente analiza y recomienda; no ejecuta compras, ventas, "
            "movimientos de liquidez ni cambios de límites."
        )
        self._status.setObjectName("intelligenceGuardrail")
        root.addWidget(self._status)

    @staticmethod
    def _metric_card(label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("intelligenceMetricCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        label_widget = QLabel(label)
        label_widget.setObjectName("metricLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("metricValue")
        value_widget.setWordWrap(True)
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)
        return frame

    @staticmethod
    def _set_card_value(card: QFrame, value: str) -> None:
        widget = card.findChild(QLabel, "metricValue")
        if widget is not None:
            widget.setText(value)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._load_requested:
            self._load_requested = True
            self._start_analysis(force_refresh=False)

    def refresh(self) -> None:
        """Refresh the intelligence snapshot after global AIP source refreshes."""

        self._start_analysis(force_refresh=True)

    def _start_analysis(self, *, force_refresh: bool) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self._refresh_button.setEnabled(False)
        self._ask_button.setEnabled(False)
        self._status.setText("Analizando evidencia de Portafolio · Mercado · Liquidez…")

        thread = QThread(self)
        worker = _AnalysisWorker(self._presenter, force_refresh=force_refresh)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._bind_model)
        worker.failed.connect(self._analysis_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._analysis_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _bind_model(self, payload: object) -> None:
        if not isinstance(payload, FinancialIntelligenceViewModel):
            self._analysis_failed("El motor devolvió un modelo de inteligencia no válido")
            return
        self._model = payload
        self._loaded = True
        self._set_card_value(self._cutoff_card, payload.cutoff_date)
        self._set_card_value(
            self._mode_card,
            "Determinístico" if not payload.llm_available else "IA + reglas",
        )
        self._set_card_value(self._alerts_card, str(payload.alert_count))
        self._set_card_value(self._opportunities_card, str(payload.opportunity_count))
        self._set_card_value(self._coverage_card, payload.coverage)
        self._set_card_value(self._provider_card, payload.llm_provider)

        self._table.setRowCount(len(payload.findings))
        for row_index, finding in enumerate(payload.findings):
            for column, value in enumerate(
                (finding.severity, finding.domain, finding.title, finding.evidence)
            ):
                self._table.setItem(row_index, column, QTableWidgetItem(value))

        warning_text = ""
        if payload.warnings:
            warning_text = "\n\nAdvertencias de fuente:\n" + "\n".join(
                f"• {warning}" for warning in payload.warnings
            )
        self._analysis_text.setPlainText(payload.executive_summary + warning_text)
        if payload.findings:
            self._table.selectRow(0)

    @Slot()
    def _analysis_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._refresh_button.setEnabled(True)
        self._ask_button.setEnabled(self._loaded)
        if self._loaded:
            self._status.setText(
                "Análisis actualizado. Human-in-the-loop activo: las recomendaciones no ejecutan operaciones."
            )

    @Slot(str)
    def _analysis_failed(self, message: str) -> None:
        self._loaded = False
        self._analysis_text.setPlainText(f"No fue posible generar el análisis: {message}")
        self._status.setText("Agente IA no disponible para el corte actual.")

    def _show_selected_finding(self) -> None:
        model = self._model
        selection_model = self._table.selectionModel()
        selected = selection_model.selectedRows() if selection_model is not None else []
        if model is None or not selected:
            return
        index = selected[0].row()
        if index < 0 or index >= len(model.findings):
            return
        finding = model.findings[index]
        parts = [
            model.executive_summary,
            "",
            f"{finding.severity} · {finding.domain}",
            finding.title,
            finding.summary,
            "",
            "Estrategia sugerida:",
            finding.recommendation,
            "",
            "Evidencia:",
            finding.evidence,
        ]
        if finding.policy_reference:
            parts.extend(("", "Referencia:", finding.policy_reference))
        self._analysis_text.setPlainText("\n".join(parts))

    def _ask(self) -> None:
        self._ask_text(self._question.text())

    def _ask_text(self, question: str) -> None:
        question = question.strip()
        if not question or not self._loaded:
            return
        try:
            answer = self._presenter.ask(question)
        except Exception as exc:
            QMessageBox.warning(self, "Agente IA", f"No fue posible responder:\n{exc}")
            return
        self._question.setText(question)
        self._analysis_text.setPlainText(f"Pregunta:\n{question}\n\n{answer}")

    def _apply_style(self) -> None:
        self.setStyleSheet(
            "QLabel#intelligenceTitle {font-size:16px; font-weight:800; color:#00345F;}"
            "QLabel#intelligenceSubtitle {font-size:10px; color:#657D8C;}"
            "QFrame#intelligenceMetricCard {background:#FFFFFF; border:1px solid #D5DEE3; "
            "border-radius:7px;}"
            "QLabel#metricLabel {font-size:9px; color:#657D8C;}"
            "QLabel#metricValue {font-size:13px; font-weight:700; color:#00345F;}"
            "QGroupBox {font-weight:700; color:#005EB8; border:1px solid #D5DEE3; "
            "border-radius:7px; margin-top:8px; padding-top:8px;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 4px;}"
            "QPushButton {background:#005EB8; color:#FFFFFF; border:none; border-radius:5px; "
            "padding:7px 12px; font-weight:700;}"
            "QPushButton:hover {background:#00477F;}"
            'QPushButton[secondary="true"] {background:#EEF6FB; color:#005EB8; '
            "border:1px solid #B7D9EE;}"
            "QLineEdit {padding:7px; border:1px solid #C8D5DE; border-radius:5px;}"
            "QTextEdit, QTableWidget {background:#FFFFFF; border:1px solid #D5DEE3; "
            "border-radius:5px; color:#183247;}"
            "QLabel#intelligenceGuardrail {background:#F5FAFD; border:1px solid #CFE4F2; "
            "border-radius:5px; padding:7px; color:#49697E;}"
        )
