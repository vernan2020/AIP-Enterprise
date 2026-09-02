from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.product.configured.protocols import EconomicIndicatorsProvider
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.economic.economic_snapshot_store import EconomicSnapshotStore
from aip.product.economic.economic_viewmodel import (
    EconomicCurvePoint,
    EconomicIndicatorCard,
    EconomicSnapshot,
    EconomicViewModel,
)
from aip.ui.modules.macro_intelligence.presenters.macro_intelligence_presenter import (
    MacroIntelligencePresenter,
)
from aip.ui.modules.macro_intelligence.viewmodels.macro_intelligence_view_model import (
    MacroProjectionViewModel,
)


_MONTHS = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)


def _format_period(value: date, *, include_year: bool = True) -> str:
    month = _MONTHS[value.month - 1]
    return f"{month}-{value.year}" if include_year else f"{month}-{str(value.year)[2:]}"


def _translate_status(value: object) -> str:
    text = str(value or "N/D")
    return {
        "AVAILABLE": "DISPONIBLE",
        "UNAVAILABLE": "NO DISPONIBLE",
        "APPROVED": "APROBADO",
        "DRAFT": "BORRADOR",
        "LOADING": "CARGANDO",
        "READY": "LISTO",
    }.get(text.strip().upper(), text)


class _EconomicWorkerSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class _EconomicLoadWorker(QRunnable):
    def __init__(self, viewmodel: EconomicViewModel) -> None:
        super().__init__()
        self._viewmodel = viewmodel
        self.signals = _EconomicWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            self.signals.completed.emit(self._viewmodel.load())
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


class _MacroMetricCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("macroMetricCard")
        self.setMinimumHeight(104)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 8, 11, 8)
        layout.setSpacing(2)
        caption = QLabel(title)
        caption.setStyleSheet("color:#667788; font-size:9px; border:none;")
        self._value = QLabel("N/D")
        value_font = QFont()
        value_font.setPointSize(17)
        value_font.setBold(True)
        self._value.setFont(value_font)
        self._value.setStyleSheet("color:#142E46; border:none;")
        self._change = QLabel("—")
        self._change.setStyleSheet("color:#53697C; font-size:9px; border:none;")
        self._date = QLabel("Sin dato")
        self._date.setStyleSheet("color:#8A98A6; font-size:8px; border:none;")
        layout.addWidget(caption)
        layout.addWidget(self._value)
        layout.addWidget(self._change)
        layout.addStretch(1)
        layout.addWidget(self._date)

    def set_indicator(self, indicator: EconomicIndicatorCard | None) -> None:
        if indicator is None or indicator.value is None:
            self._value.setText("N/D")
            self._change.setText("—")
            self._date.setText("Sin dato")
            return
        if indicator.code == "FX_SELL":
            self._value.setText(f"₡{indicator.value:,.2f}")
        elif indicator.unit == "%":
            self._value.setText(f"{indicator.value:.2f}%")
        else:
            self._value.setText(f"{indicator.value:,.2f}")
        change = indicator.absolute_change
        symbol = {"UP": "▲", "DOWN": "▼", "STABLE": "■"}.get(indicator.trend, "•")
        if change is None:
            self._change.setText("—")
        elif indicator.code == "FX_SELL":
            self._change.setText(f"{symbol} {change:+.2f}")
        else:
            self._change.setText(f"{symbol} {change:+.2f} pp")
        date_text = indicator.observation_date.strftime("%d/%m/%Y") if indicator.observation_date else "Sin fecha"
        source = indicator.source or "BCCR"
        if indicator.derived:
            source += " · derivado"
        self._date.setText(f"{date_text} · {source}")


class _ProjectionChart(QWidget):
    """Gráfico de presentación para una trayectoria macroeconómica aprobada."""

    _LABELS = {
        "FX_SELL": "USD/CRC",
        "TPM": "TPM",
        "TBP": "TBP",
        "TRI_CRC_12M": "TRI CRC 12M",
        "TRI_USD_12M": "TRI USD 12M",
        "INFLATION": "Inflación",
        "IMAE": "IMAE",
    }

    def __init__(self) -> None:
        super().__init__()
        self._projection = MacroProjectionViewModel()
        self._driver_code = "TPM"
        self.setMinimumHeight(300)

    def set_projection(self, projection: MacroProjectionViewModel, driver_code: str) -> None:
        self._projection = projection
        self._driver_code = driver_code
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        rows = self._projection.rows
        if not rows:
            painter.setPen(QColor("#718096"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Proyección institucional no disponible")
            return

        values = [row.value_for(self._driver_code) for row in rows]
        minimum = min(values)
        maximum = max(values)
        span = max(maximum - minimum, 0.01)
        minimum -= span * 0.12
        maximum += span * 0.12
        span = maximum - minimum
        left, right, top, bottom = 58.0, 22.0, 24.0, 48.0
        width = max(40.0, self.width() - left - right)
        height = max(40.0, self.height() - top - bottom)

        painter.setPen(QPen(QColor("#E1E7EC"), 1))
        label_font = QFont(self.font())
        label_font.setPointSize(8)
        painter.setFont(label_font)
        for index in range(5):
            fraction = index / 4
            y = top + height * fraction
            painter.drawLine(QPointF(left, y), QPointF(left + width, y))
            value = maximum - span * fraction
            painter.setPen(QColor("#637587"))
            suffix = "" if self._driver_code == "FX_SELL" else "%"
            painter.drawText(
                QRectF(4, y - 9, left - 10, 18),
                Qt.AlignmentFlag.AlignRight,
                f"{value:.2f}{suffix}",
            )
            painter.setPen(QPen(QColor("#E1E7EC"), 1))

        points: list[QPointF] = []
        count = len(rows)
        for index, row in enumerate(rows):
            x = left + (width * index / max(1, count - 1))
            value = row.value_for(self._driver_code)
            y = top + height - ((value - minimum) / span) * height
            points.append(QPointF(x, y))

        if len(points) >= 2:
            painter.setPen(QPen(QColor("#1F5A8A"), 2.4))
            painter.drawPolyline(QPolygonF(points))
        painter.setBrush(QColor("#C9892B"))
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        for point in points:
            painter.drawEllipse(point, 4.0, 4.0)

        painter.setPen(QColor("#53697C"))
        indexes = sorted({0, count - 1, count // 3, (count * 2) // 3})
        for index in indexes:
            row = rows[index]
            x = left + (width * index / max(1, count - 1))
            painter.drawText(
                QRectF(x - 36, top + height + 8, 72, 20),
                Qt.AlignmentFlag.AlignHCenter,
                _format_period(row.period, include_year=False),
            )

        title_font = QFont(self.font())
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#17324D"))
        painter.drawText(
            QRectF(left, 2, width, 20),
            Qt.AlignmentFlag.AlignLeft,
            self._LABELS.get(self._driver_code, self._driver_code),
        )


class MacroIntelligenceWorkspace(QWidget):
    """Espacio macroeconómico avanzado con observaciones BCCR y escenario aprobado."""

    _CARD_DEFINITIONS = (
        ("FX_SELL", "USD / CRC"),
        ("INFLATION", "Inflación"),
        ("TPM", "TPM"),
        ("TBP", "TBP"),
        ("IMAE", "IMAE"),
        ("GDP", "PIB real"),
        ("UNEMPLOYMENT", "Desempleo"),
    )
    _DRIVER_LABELS = (
        ("TPM", "TPM"),
        ("TBP", "TBP"),
        ("TRI_CRC_12M", "TRI CRC 12M"),
        ("TRI_USD_12M", "TRI USD 12M"),
        ("INFLATION", "Inflación"),
        ("IMAE", "IMAE"),
        ("FX_SELL", "USD/CRC"),
    )

    def __init__(
        self,
        *,
        application_factory: DemoApplicationFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("macroIntelligenceWorkspace")
        self._application_factory = application_factory
        self._presenter = MacroIntelligencePresenter(application_factory)
        self._snapshot_store = EconomicSnapshotStore()
        self._thread_pool = QThreadPool.globalInstance()
        self._active_worker: _EconomicLoadWorker | None = None
        self._loading = False
        self._refresh_pending = False
        self._snapshot: EconomicSnapshot | None = None
        self._projection = MacroProjectionViewModel(status="LOADING")
        self._cards: dict[str, _MacroMetricCard] = {}
        self._build_ui()
        self._apply_styles()
        self._load_persisted_snapshot()
        self._load_projection()

    @property
    def projection(self) -> MacroProjectionViewModel:
        return self._projection

    @property
    def snapshot(self) -> EconomicSnapshot | None:
        return self._snapshot

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(14, 10, 14, 16)
        root.setSpacing(9)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        header = QFrame()
        header.setObjectName("macroHeader")
        header_layout = QHBoxLayout(header)
        title_box = QVBoxLayout()
        title = QLabel("INTELIGENCIA MACROECONÓMICA")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        self._status_label = QLabel("Cargando información observada y escenario institucional...")
        self._status_label.setStyleSheet("color:#667788; font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(self._status_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)
        self._scenario_badge = QLabel("Escenario: -")
        self._scenario_badge.setObjectName("macroScenarioBadge")
        header_layout.addWidget(self._scenario_badge)
        self._refresh_button = QPushButton("ACTUALIZAR BCCR")
        self._refresh_button.clicked.connect(self.refresh)
        header_layout.addWidget(self._refresh_button)
        root.addWidget(header)

        metric_grid = QGridLayout()
        metric_grid.setHorizontalSpacing(7)
        metric_grid.setVerticalSpacing(7)
        for index, (code, label) in enumerate(self._CARD_DEFINITIONS):
            card = _MacroMetricCard(label)
            self._cards[code] = card
            metric_grid.addWidget(card, index // 4, index % 4)
        root.addLayout(metric_grid)

        governance_grid = QGridLayout()
        governance_grid.setHorizontalSpacing(7)
        for index, (key, title_text, helper) in enumerate(
            (
                ("scenario", "Escenario", "Identificador gobernado"),
                ("version", "Versión", "Última versión aprobada"),
                ("dataset", "Datos Base", "Fecha base de estimación"),
                ("horizon", "Horizonte", "Trayectoria mensual"),
            )
        ):
            governance_grid.addWidget(self._governance_card(key, title_text, helper), 0, index)
        root.addLayout(governance_grid)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        root.addWidget(self._tabs, 1)
        self._build_projection_tab()
        self._build_projection_table_tab()
        self._build_market_curves_tab()
        self._build_transmission_tab()

    def _governance_card(self, key: str, caption: str, helper: str) -> QFrame:
        if not hasattr(self, "_governance_labels"):
            self._governance_labels: dict[str, QLabel] = {}
        card = QFrame()
        card.setObjectName("macroGovernanceCard")
        card.setMinimumHeight(70)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 6, 10, 6)
        title = QLabel(caption)
        title.setStyleSheet("color:#667788; font-size:8px; border:none;")
        value = QLabel("-")
        value.setStyleSheet("color:#17324D; font-weight:700; font-size:11px; border:none;")
        hint = QLabel(helper)
        hint.setStyleSheet("color:#93A0AC; font-size:8px; border:none;")
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(hint)
        self._governance_labels[key] = value
        return card

    def _build_projection_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        selector = QHBoxLayout()
        selector.addWidget(QLabel("Variable proyectada:"))
        self._driver_combo = QComboBox()
        for code, label in self._DRIVER_LABELS:
            self._driver_combo.addItem(label, code)
        self._driver_combo.currentIndexChanged.connect(self._refresh_projection_chart)
        selector.addWidget(self._driver_combo)
        selector.addStretch(1)
        self._projection_range = QLabel("-")
        self._projection_range.setStyleSheet("color:#53697C; font-weight:600;")
        selector.addWidget(self._projection_range)
        layout.addLayout(selector)

        group = QGroupBox("PROYECCIÓN MACROECONÓMICA INSTITUCIONAL")
        group_layout = QVBoxLayout(group)
        self._projection_chart = _ProjectionChart()
        group_layout.addWidget(self._projection_chart)
        self._projection_note = QLabel("")
        self._projection_note.setWordWrap(True)
        self._projection_note.setStyleSheet("color:#617386; padding:3px 8px;")
        group_layout.addWidget(self._projection_note)
        layout.addWidget(group, 1)
        self._tabs.addTab(page, "Proyección 12 meses")

    def _build_projection_table_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        self._projection_table = QTableWidget(0, 8)
        self._projection_table.setHorizontalHeaderLabels(
            ["Periodo", "USD/CRC", "TPM", "TBP", "TRI CRC 12M", "TRI USD 12M", "Inflación", "IMAE"]
        )
        self._projection_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._projection_table.verticalHeader().setVisible(False)
        self._projection_table.setAlternatingRowColors(True)
        self._projection_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._projection_table)
        self._tabs.addTab(page, "Matriz de Variables")

    def _build_market_curves_tab(self) -> None:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        self._tri_crc_table = self._curve_table()
        self._tri_usd_table = self._curve_table()
        layout.addWidget(self._table_group("TRI CRC · observado", self._tri_crc_table), 1)
        layout.addWidget(self._table_group("TRI USD · observado", self._tri_usd_table), 1)
        self._tabs.addTab(page, "Curvas TRI")

    def _build_transmission_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        strip = QHBoxLayout()
        stages = (
            ("1", "MACRO", "7 variables aprobadas"),
            ("2", "MERCADOS", "Curvas · tasas · tipo de cambio"),
            ("3", "BALANCE", "ALM · reprecio · liquidez"),
            ("4", "RESULTADOS", "NII · EVE · ROA · solvencia"),
        )
        for index, (number, title, detail) in enumerate(stages):
            card = QFrame()
            card.setObjectName("macroTransmissionCard")
            card_layout = QVBoxLayout(card)
            step = QLabel(number)
            step.setStyleSheet("font-size:18px; font-weight:700; color:#1F5A8A; border:none;")
            name = QLabel(title)
            name.setStyleSheet("font-weight:700; color:#17324D; border:none;")
            text = QLabel(detail)
            text.setStyleSheet("color:#667788; font-size:9px; border:none;")
            text.setWordWrap(True)
            card_layout.addWidget(step)
            card_layout.addWidget(name)
            card_layout.addWidget(text)
            strip.addWidget(card, 1)
            if index < len(stages) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("font-size:22px; color:#8293A2;")
                strip.addWidget(arrow)
        layout.addLayout(strip)
        governance = QGroupBox("Gobierno del escenario y alcance del módulo")
        governance_layout = QVBoxLayout(governance)
        self._governance_text = QLabel(
            "La trayectoria macroeconómica se consume desde el escenario institucional APROBADO. "
            "El impacto financiero sobre Coopealianza se mostrará aquí cuando el Motor de Impacto Financiero "
            "publique resultados auditables; la interfaz no estima impactos por su cuenta."
        )
        self._governance_text.setWordWrap(True)
        self._governance_text.setStyleSheet("color:#53697C; padding:10px;")
        governance_layout.addWidget(self._governance_text)
        layout.addWidget(governance)
        layout.addStretch(1)
        self._tabs.addTab(page, "Transmisión")

    @staticmethod
    def _curve_table() -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Plazo", "Actual", "Anterior", "Δ", "Tendencia"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return table

    @staticmethod
    def _table_group(title: str, table: QTableWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(table)
        return group

    def _load_persisted_snapshot(self) -> None:
        snapshot = self._snapshot_store.load()
        if snapshot is not None:
            self._apply_snapshot(snapshot, persisted=True)

    def _load_projection(self) -> None:
        self._projection = self._presenter.build_projection()
        self._bind_projection()

    def _bind_projection(self) -> None:
        projection = self._projection
        if projection.status != "AVAILABLE":
            self._scenario_badge.setText("Escenario: no disponible")
            self._projection_note.setText(projection.diagnostic or "No existe escenario institucional aprobado.")
            self._projection_table.setRowCount(0)
            self._projection_chart.set_projection(projection, "TPM")
            return

        dataset = projection.dataset_as_of_date.strftime("%d/%m/%Y") if projection.dataset_as_of_date else "-"
        translated_scenario_status = _translate_status(projection.scenario_status)
        self._scenario_badge.setText(
            f"{projection.scenario_type} · v{projection.version} · {translated_scenario_status}"
        )
        self._governance_labels["scenario"].setText(projection.scenario_id)
        self._governance_labels["version"].setText(f"v{projection.version} · {translated_scenario_status}")
        self._governance_labels["dataset"].setText(dataset)
        self._governance_labels["horizon"].setText(f"{projection.horizon} meses · 7 variables")
        if projection.first_period and projection.last_period:
            self._projection_range.setText(
                f"{_format_period(projection.first_period)} → {_format_period(projection.last_period)}"
            )
        self._projection_note.setText(
            "Trayectoria gobernada consumida directamente del escenario institucional aprobado. "
            "Los valores del gráfico no se recalculan en la interfaz."
        )
        self._projection_table.setRowCount(len(projection.rows))
        for row_index, row in enumerate(projection.rows):
            values = (
                _format_period(row.period),
                f"₡{row.fx_sell:,.2f}",
                f"{row.tpm:.2f}%",
                f"{row.tbp:.2f}%",
                f"{row.tri_crc_12m:.2f}%",
                f"{row.tri_usd_12m:.2f}%",
                f"{row.inflation:.2f}%",
                f"{row.imae:.2f}%",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._projection_table.setItem(row_index, column, item)
        self._refresh_projection_chart()

    @Slot()
    def _refresh_projection_chart(self) -> None:
        code = str(self._driver_combo.currentData() or "TPM")
        self._projection_chart.set_projection(self._projection, code)

    @Slot()
    def refresh(self) -> None:
        self._load_projection()
        if self._loading:
            self._refresh_pending = True
            return
        self._refresh_pending = False
        self._loading = True
        self._refresh_button.setEnabled(False)
        self._refresh_button.setText("ACTUALIZANDO...")
        self._status_label.setText("Actualizando información observada BCCR...")
        try:
            provider = self._application_factory.container.resolve(EconomicIndicatorsProvider)
            worker = _EconomicLoadWorker(EconomicViewModel(provider))
        except Exception as exc:
            self._handle_load_error(f"{type(exc).__name__}: {exc}")
            return
        worker.signals.completed.connect(self._handle_snapshot)
        worker.signals.failed.connect(self._handle_load_error)
        self._active_worker = worker
        self._thread_pool.start(worker)

    @Slot(object)
    def _handle_snapshot(self, snapshot: object) -> None:
        if not isinstance(snapshot, EconomicSnapshot):
            self._handle_load_error("Respuesta inesperada del modelo económico")
            return
        try:
            self._apply_snapshot(snapshot, persisted=False)
            self._snapshot_store.save(snapshot)
        finally:
            self._finish_refresh()

    @Slot(str)
    def _handle_load_error(self, message: str) -> None:
        if self._snapshot is not None:
            self._status_label.setText(
                f"BCCR no disponible · mostrando última información válida · {message}"
            )
        else:
            self._status_label.setText(f"Información observada no disponible · {message}")
        self._finish_refresh()

    def _finish_refresh(self) -> None:
        self._loading = False
        self._active_worker = None
        self._refresh_button.setEnabled(True)
        self._refresh_button.setText("ACTUALIZAR BCCR")
        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh)

    def _apply_snapshot(self, snapshot: EconomicSnapshot, *, persisted: bool) -> None:
        self._snapshot = snapshot
        by_code = {indicator.code: indicator for indicator in snapshot.market_snapshot}
        for code, _ in self._CARD_DEFINITIONS:
            self._cards[code].set_indicator(by_code.get(code))
        self._populate_curve(self._tri_crc_table, snapshot.tri_crc_curve)
        self._populate_curve(self._tri_usd_table, snapshot.tri_usd_curve)
        cutoff = snapshot.cutoff_date.strftime("%d/%m/%Y") if snapshot.cutoff_date else "N/D"
        parts = [f"Fuente observada: {snapshot.source}", f"Última información: {cutoff}"]
        parts.append("Información local" if persisted else f"Caché: {snapshot.cache_entries} entradas")
        parts.append("Diagnósticos: OK" if not snapshot.diagnostics else f"Diagnósticos: {len(snapshot.diagnostics)}")
        self._status_label.setText(" · ".join(parts))

    @staticmethod
    def _populate_curve(table: QTableWidget, curve: tuple[EconomicCurvePoint, ...]) -> None:
        table.setRowCount(len(curve))
        for row_index, point in enumerate(curve):
            values = (
                point.tenor,
                MacroIntelligenceWorkspace._format_decimal(point.value),
                MacroIntelligenceWorkspace._format_decimal(point.previous_value),
                MacroIntelligenceWorkspace._format_change(point.absolute_change),
                {"UP": "▲ SUBE", "DOWN": "▼ BAJA", "STABLE": "■ ESTABLE"}.get(point.trend, point.trend or "N/D"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, column, item)

    @staticmethod
    def _format_decimal(value: Decimal | None) -> str:
        return "N/D" if value is None else f"{value:.2f}%"

    @staticmethod
    def _format_change(value: Decimal | None) -> str:
        return "N/D" if value is None else f"{value:+.2f} pp"

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            "QFrame#macroHeader, QFrame#macroMetricCard, QFrame#macroGovernanceCard, "
            "QFrame#macroTransmissionCard {background:#FFFFFF; border:1px solid #D7E0E8; border-radius:8px;}"
            "QLabel#macroScenarioBadge {padding:7px 11px; background:#EEF4F8; border:1px solid #C8D9E6; "
            "border-radius:6px; color:#174E78; font-weight:700;}"
            "QGroupBox {border:1px solid #D7E0E8; border-radius:8px; margin-top:8px; font-weight:700; "
            "color:#22384C; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
            "QTabBar::tab {padding:8px 18px; font-weight:600;}"
            "QTabBar::tab:selected {color:#174E78; border-bottom:2px solid #1F5A8A;}"
            "QPushButton {min-height:28px; padding:0 10px;} QComboBox {min-height:28px; min-width:180px;}"
        )
