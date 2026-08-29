from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QFont
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
    QVBoxLayout,
    QWidget,
)

from aip.product.configured.protocols import (
    EconomicIndicatorsProvider,
)
from aip.product.demo.bootstrap.application_factory import (
    DemoApplicationFactory,
)
from aip.product.economic.economic_snapshot_store import (
    EconomicSnapshotStore,
)
from aip.product.economic.economic_viewmodel import (
    EconomicCurvePoint,
    EconomicIndicatorCard,
    EconomicSnapshot,
    EconomicViewModel,
)


class _MacroWorkerSignals(QObject):
    """Señales Qt emitidas por el worker de Macro Intelligence."""

    completed = Signal(object)
    failed = Signal(str)


class _MacroLoadWorker(QRunnable):
    """
    Worker de carga utilizando QThreadPool.

    QThreadPool evita vincular la vida del hilo a la vida
    inmediata del widget, reduciendo problemas al cerrar
    pestañas mientras una consulta está en ejecución.
    """

    def __init__(
        self,
        viewmodel: EconomicViewModel,
    ) -> None:
        super().__init__()

        self._viewmodel = viewmodel
        self.signals = _MacroWorkerSignals()

        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            snapshot = self._viewmodel.load()

            self.signals.completed.emit(snapshot)

        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


class MacroMetricCard(QFrame):
    """Tarjeta compacta para un indicador macroeconómico."""

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("macroMetricCard")

        self.setFrameShape(QFrame.Shape.StyledPanel)

        self.setMinimumHeight(112)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )

        layout.setSpacing(3)

        self._title = QLabel(title)

        self._title.setObjectName("macroMetricTitle")

        self._value = QLabel("N/D")

        self._value.setObjectName("macroMetricValue")

        value_font = QFont()

        value_font.setPointSize(18)
        value_font.setBold(True)

        self._value.setFont(value_font)

        self._change = QLabel("—")

        self._change.setObjectName("macroMetricChange")

        self._date = QLabel("Sin dato")

        self._date.setObjectName("macroMetricDate")

        self._source = QLabel("BCCR")

        self._source.setObjectName("macroMetricSource")

        layout.addWidget(self._title)

        layout.addWidget(self._value)

        layout.addWidget(self._change)

        layout.addStretch(1)

        layout.addWidget(self._date)

        layout.addWidget(self._source)

    def set_indicator(
        self,
        indicator: EconomicIndicatorCard | None,
    ) -> None:
        if indicator is None:
            self.clear()
            return

        self._value.setText(self._format_value(indicator))

        self._change.setText(self._format_change(indicator))

        observation_date = indicator.observation_date

        if observation_date is None:
            self._date.setText("Sin fecha")

        else:
            self._date.setText(observation_date.strftime("%d/%m/%Y"))

        source = indicator.source or "BCCR"

        if indicator.derived:
            source += " · derivado"

        self._source.setText(source)

    def clear(self) -> None:
        self._value.setText("N/D")

        self._change.setText("—")

        self._date.setText("Sin dato")

        self._source.setText("BCCR")

    @staticmethod
    def _format_value(
        indicator: EconomicIndicatorCard,
    ) -> str:
        value = indicator.value

        if value is None:
            return "N/D"

        if indicator.code == "FX_SELL":
            return f"₡{value:,.2f}"

        if indicator.unit == "%":
            return f"{value:.2f}%"

        return f"{value:,.2f}"

    @staticmethod
    def _format_change(
        indicator: EconomicIndicatorCard,
    ) -> str:
        change = indicator.absolute_change

        if change is None:
            return "—"

        symbol = {
            "UP": "▲",
            "DOWN": "▼",
            "STABLE": "■",
        }.get(
            indicator.trend,
            "•",
        )

        if indicator.code == "FX_SELL":
            return f"{symbol} " f"{change:+.2f}"

        return f"{symbol} " f"{change:+.2f} pp"


class MacroPlaceholderPanel(QFrame):
    """
    Panel reservado para funcionalidades cuyos
    motores de dominio aún no están implementados.
    """

    def __init__(
        self,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("macroPlaceholderPanel")

        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )

        title_label = QLabel(title)

        title_label.setObjectName("macroSectionTitle")

        title_font = QFont()

        title_font.setBold(True)

        title_label.setFont(title_font)

        status = QLabel("N/D")

        status.setObjectName("macroPlaceholderValue")

        status_font = QFont()

        status_font.setPointSize(20)
        status_font.setBold(True)

        status.setFont(status_font)

        description_label = QLabel(description)

        description_label.setWordWrap(True)

        description_label.setObjectName("macroSecondaryText")

        layout.addWidget(title_label)

        layout.addWidget(status)

        layout.addWidget(description_label)

        layout.addStretch(1)


class MacroIntelligenceView(QWidget):
    """
    Vista principal de Macro Intelligence.

    Esta capa es exclusivamente de presentación.

    No contiene:
    - forecasting;
    - regresiones;
    - correlaciones;
    - simulación;
    - cálculo ALM;
    - cálculo de impacto financiero.

    Todas esas funciones serán servicios separados
    del dominio económico/econométrico.
    """

    _CARD_DEFINITIONS = (
        (
            "FX_SELL",
            "USD / CRC",
        ),
        (
            "INFLATION",
            "Inflación",
        ),
        (
            "TPM",
            "TPM",
        ),
        (
            "TBP",
            "TBP",
        ),
        (
            "IMAE",
            "IMAE",
        ),
        (
            "GDP",
            "PIB real",
        ),
        (
            "UNEMPLOYMENT",
            "Desempleo",
        ),
    )

    def __init__(
        self,
        *,
        application_factory: DemoApplicationFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("macroIntelligenceView")

        self._application_factory = application_factory

        self._snapshot_store = EconomicSnapshotStore()

        self._thread_pool = QThreadPool.globalInstance()

        self._loading = False
        self._refresh_pending = False

        self._active_worker: _MacroLoadWorker | None = None

        self._snapshot: EconomicSnapshot | None = None

        self._cards: dict[
            str,
            MacroMetricCard,
        ] = {}

        self._build_ui()

        self._apply_local_styles()

        self._load_persisted_snapshot()

    # ============================================================
    # PUBLIC API
    # ============================================================

    @property
    def snapshot(
        self,
    ) -> EconomicSnapshot | None:
        return self._snapshot

    @property
    def is_loading(
        self,
    ) -> bool:
        return self._loading

    def _load_persisted_snapshot(
        self,
    ) -> None:
        """
        Load the most recent valid persisted economic snapshot.

        This method never performs network I/O.
        """

        snapshot = self._snapshot_store.load()

        if snapshot is None:
            return

        self._apply_snapshot(
            snapshot,
            persisted=True,
        )

    def _apply_snapshot(
        self,
        snapshot: EconomicSnapshot,
        *,
        persisted: bool,
    ) -> None:
        """
        Apply an EconomicSnapshot to the view.

        Presentation only. No business calculations occur here.
        """

        self._snapshot = snapshot

        by_code = {item.code: item for item in snapshot.market_snapshot}

        for code, _ in self._CARD_DEFINITIONS:
            self._cards[code].set_indicator(by_code.get(code))

        self._populate_curve(
            self._tri_crc_table,
            snapshot.tri_crc_curve,
        )

        self._populate_curve(
            self._tri_usd_table,
            snapshot.tri_usd_curve,
        )

        cutoff_text = (
            snapshot.cutoff_date.strftime("%d/%m/%Y") if snapshot.cutoff_date is not None else "N/D"
        )

        status_parts = [
            (f"Fuente: " f"{snapshot.source}"),
            (f"Última información: " f"{cutoff_text}"),
        ]

        if persisted:
            status_parts.append("Snapshot local")
        else:
            status_parts.append(f"Cache: " f"{snapshot.cache_entries} entradas")

        if snapshot.diagnostics:
            status_parts.append((f"Diagnósticos: " f"{len(snapshot.diagnostics)}"))
        else:
            status_parts.append("Diagnósticos: OK")

        self._status_label.setText(" · ".join(status_parts))

    @Slot()
    def refresh(
        self,
    ) -> None:
        """
        Actualiza el snapshot macroeconómico.

        Compatible con MainWindow.refresh_all() y con
        el mecanismo global de cambio de fecha de AIP.
        """

        if self._loading:
            self._refresh_pending = True
            return

        self._refresh_pending = False
        self._set_loading(True)

        self._status_label.setText("Actualizando información BCCR...")

        try:
            provider = self._application_factory.container.resolve(EconomicIndicatorsProvider)
            viewmodel = EconomicViewModel(provider)
        except Exception as exc:
            self._handle_load_error(f"{type(exc).__name__}: {exc}")
            return

        worker = _MacroLoadWorker(viewmodel)

        worker.signals.completed.connect(self._handle_snapshot)

        worker.signals.failed.connect(self._handle_load_error)

        self._active_worker = worker

        self._thread_pool.start(worker)

    # ============================================================
    # BUILD UI
    # ============================================================

    def _build_ui(
        self,
    ) -> None:
        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.setSpacing(0)

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()

        content.setObjectName("macroIntelligenceContent")

        layout = QVBoxLayout(content)

        layout.setContentsMargins(
            14,
            12,
            14,
            16,
        )

        layout.setSpacing(12)

        layout.addWidget(self._build_header())

        layout.addWidget(self._build_metric_strip())

        layout.addWidget(self._build_projection_section())

        layout.addLayout(self._build_middle_section())

        layout.addWidget(self._build_transmission_section())

        layout.addWidget(self._build_tri_section())

        layout.addStretch(1)

        scroll.setWidget(content)

        root_layout.addWidget(scroll)

    def _build_header(
        self,
    ) -> QWidget:
        frame = QFrame()

        frame.setObjectName("macroHeader")

        layout = QHBoxLayout(frame)

        layout.setContentsMargins(
            14,
            10,
            14,
            10,
        )

        title_container = QWidget()

        title_layout = QVBoxLayout(title_container)

        title_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        title_layout.setSpacing(1)

        title = QLabel("MACRO INTELLIGENCE")

        title.setObjectName("macroMainTitle")

        title_font = QFont()

        title_font.setPointSize(16)

        title_font.setBold(True)

        title.setFont(title_font)

        self._status_label = QLabel("Pendiente de actualización")

        self._status_label.setObjectName("macroStatusLabel")

        title_layout.addWidget(title)

        title_layout.addWidget(self._status_label)

        layout.addWidget(
            title_container,
            1,
        )

        layout.addWidget(QLabel("Escenario:"))

        self._scenario_combo = QComboBox()

        self._scenario_combo.addItems(
            [
                "BASE",
                "FAVORABLE",
                "ADVERSO",
            ]
        )

        self._scenario_combo.setEnabled(False)

        self._scenario_combo.setToolTip("Disponible cuando se implemente " "Scenario Engine.")

        layout.addWidget(self._scenario_combo)

        layout.addWidget(QLabel("Horizonte:"))

        self._horizon_combo = QComboBox()

        self._horizon_combo.addItems(
            [
                "6 meses",
                "12 meses",
                "24 meses",
            ]
        )

        self._horizon_combo.setCurrentText("12 meses")

        self._horizon_combo.setEnabled(False)

        layout.addWidget(self._horizon_combo)

        self._simulate_button = QPushButton("SIMULAR")

        self._simulate_button.setEnabled(False)

        self._simulate_button.setToolTip("Pendiente del motor econométrico.")

        layout.addWidget(self._simulate_button)

        self._refresh_button = QPushButton("ACTUALIZAR")

        self._refresh_button.clicked.connect(self.refresh)

        layout.addWidget(self._refresh_button)

        return frame

    def _build_metric_strip(
        self,
    ) -> QWidget:
        frame = QFrame()

        frame.setObjectName("macroMetricStrip")

        layout = QGridLayout(frame)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setHorizontalSpacing(8)

        layout.setVerticalSpacing(8)

        for index, (
            code,
            title,
        ) in enumerate(self._CARD_DEFINITIONS):
            card = MacroMetricCard(title)

            self._cards[code] = card

            row = 0 if index < 4 else 1

            column = index if index < 4 else index - 4

            layout.addWidget(
                card,
                row,
                column,
            )

        return frame

    def _build_projection_section(
        self,
    ) -> QWidget:
        group = QGroupBox("PROYECCIÓN MACROECONÓMICA MULTIVARIADA")

        group.setObjectName("macroProjectionGroup")

        layout = QVBoxLayout(group)

        self._projection_status = QLabel(
            "Motor econométrico no implementado\n\n" "BASE / FAVORABLE / ADVERSO · N/D"
        )

        self._projection_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._projection_status.setMinimumHeight(170)

        self._projection_status.setObjectName("macroProjectionPlaceholder")

        self._projection_status.setWordWrap(True)

        layout.addWidget(self._projection_status)

        selector_layout = QHBoxLayout()

        selector_layout.addStretch(1)

        for label in (
            "TPM",
            "TBP",
            "TRI CRC",
            "TRI USD",
            "Inflación",
            "IMAE",
            "USD/CRC",
        ):
            button = QPushButton(label)

            button.setEnabled(False)

            selector_layout.addWidget(button)

        selector_layout.addStretch(1)

        layout.addLayout(selector_layout)

        return group

    def _build_middle_section(
        self,
    ) -> QHBoxLayout:
        layout = QHBoxLayout()

        layout.setSpacing(10)

        driver_panel = MacroPlaceholderPanel(
            "DRIVERS / CORRELACIONES",
            (
                "Pendiente del motor econométrico. "
                "Los coeficientes aparecerán únicamente "
                "cuando hayan sido estimados, validados "
                "y documentados."
            ),
        )

        impact_panel = MacroPlaceholderPanel(
            "IMPACTO COOPERATIVA",
            (
                "Pendiente del Cooperative Impact Engine: "
                "margen financiero, resultado neto, NIM, "
                "ΔEVE, ΔNII, ROA y suficiencia patrimonial."
            ),
        )

        layout.addWidget(
            driver_panel,
            1,
        )

        layout.addWidget(
            impact_panel,
            1,
        )

        return layout

    def _build_transmission_section(
        self,
    ) -> QWidget:
        panel = MacroPlaceholderPanel(
            "TRANSMISIÓN DEL ESCENARIO",
            (
                "MACRO → MERCADOS → BALANCE → RESULTADOS\n\n"
                "Se habilitará cuando Scenario Engine y "
                "Cooperative Impact Engine produzcan "
                "resultados auditables."
            ),
        )

        panel.setMinimumHeight(145)

        return panel

    def _build_tri_section(
        self,
    ) -> QWidget:
        group = QGroupBox("CURVAS TRI · INFORMACIÓN DE MERCADO")

        layout = QHBoxLayout(group)

        self._tri_crc_table = self._create_curve_table("CRC")

        self._tri_usd_table = self._create_curve_table("USD")

        layout.addWidget(
            self._table_container(
                "TRI CRC",
                self._tri_crc_table,
            ),
            1,
        )

        layout.addWidget(
            self._table_container(
                "TRI USD",
                self._tri_usd_table,
            ),
            1,
        )

        return group

    @staticmethod
    def _create_curve_table(
        currency: str,
    ) -> QTableWidget:
        table = QTableWidget(
            0,
            5,
        )

        table.setObjectName(f"tri{currency}Table")

        table.setHorizontalHeaderLabels(
            [
                "Plazo",
                "Actual",
                "Anterior",
                "Δ",
                "Tendencia",
            ]
        )

        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        table.verticalHeader().setVisible(False)

        table.setAlternatingRowColors(True)

        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        table.setMinimumHeight(255)

        return table

    @staticmethod
    def _table_container(
        title: str,
        table: QTableWidget,
    ) -> QWidget:
        container = QWidget()

        layout = QVBoxLayout(container)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        title_label = QLabel(title)

        font = QFont()

        font.setBold(True)

        title_label.setFont(font)

        layout.addWidget(title_label)

        layout.addWidget(table)

        return container

    # ============================================================
    # SNAPSHOT HANDLING
    # ============================================================

    @Slot(object)
    def _handle_snapshot(
        self,
        snapshot: object,
    ) -> None:
        if not isinstance(
            snapshot,
            EconomicSnapshot,
        ):
            self._handle_load_error("Respuesta inesperada del EconomicViewModel")
            return

        try:
            self._apply_snapshot(
                snapshot,
                persisted=False,
            )

            self._snapshot_store.save(snapshot)

        finally:
            self._finish_refresh_cycle()

    @Slot(str)
    def _handle_load_error(
        self,
        message: str,
    ) -> None:
        try:
            if self._snapshot is not None:
                self._status_label.setText(
                    (
                        "Actualización BCCR no disponible · "
                        "mostrando último snapshot válido · "
                        f"{message}"
                    )
                )
            else:
                self._status_label.setText(("Macro Intelligence no disponible · " f"{message}"))

                for card in self._cards.values():
                    card.clear()

                self._tri_crc_table.setRowCount(0)

                self._tri_usd_table.setRowCount(0)

        finally:
            self._finish_refresh_cycle()

    def _finish_refresh_cycle(
        self,
    ) -> None:
        self._set_loading(False)
        self._active_worker = None

        if not self._refresh_pending:
            return

        self._refresh_pending = False
        QTimer.singleShot(
            0,
            self.refresh,
        )

    def _set_loading(
        self,
        loading: bool,
    ) -> None:
        self._loading = loading

        self._refresh_button.setEnabled(not loading)

        self._refresh_button.setText("ACTUALIZANDO..." if loading else "ACTUALIZAR")

    @staticmethod
    def _populate_curve(
        table: QTableWidget,
        curve: tuple[
            EconomicCurvePoint,
            ...,
        ],
    ) -> None:
        table.setRowCount(len(curve))

        for row, point in enumerate(curve):
            values = (
                point.tenor,
                MacroIntelligenceView._format_decimal(point.value),
                MacroIntelligenceView._format_decimal(point.previous_value),
                MacroIntelligenceView._format_change_value(point.absolute_change),
                MacroIntelligenceView._format_trend(point.trend),
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column > 0:
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))

                table.setItem(
                    row,
                    column,
                    item,
                )

    @staticmethod
    def _format_decimal(
        value: Decimal | None,
    ) -> str:
        if value is None:
            return "N/D"

        return f"{value:.2f}%"

    @staticmethod
    def _format_change_value(
        value: Decimal | None,
    ) -> str:
        if value is None:
            return "N/D"

        return f"{value:+.2f} pp"

    @staticmethod
    def _format_trend(
        value: str,
    ) -> str:
        return {
            "UP": "▲ SUBE",
            "DOWN": "▼ BAJA",
            "STABLE": "■ ESTABLE",
        }.get(
            value,
            value or "N/D",
        )

    # ============================================================
    # LOCAL STYLE
    # ============================================================

    def _apply_local_styles(
        self,
    ) -> None:
        self.setStyleSheet("""
            #macroIntelligenceContent {
                background: transparent;
            }

            #macroHeader {
                border: 1px solid rgba(120, 130, 140, 70);
                border-radius: 4px;
            }

            #macroMainTitle {
                letter-spacing: 1px;
            }

            #macroStatusLabel,
            #macroMetricDate,
            #macroMetricSource,
            #macroSecondaryText {
                opacity: 0.75;
            }

            #macroMetricCard,
            #macroPlaceholderPanel {
                border: 1px solid rgba(120, 130, 140, 70);
                border-radius: 4px;
            }

            #macroMetricTitle,
            #macroSectionTitle {
                font-weight: 600;
            }

            #macroMetricValue {
                font-weight: 700;
            }

            #macroPlaceholderValue {
                font-weight: 700;
                opacity: 0.55;
            }

            #macroProjectionPlaceholder {
                border: 1px dashed rgba(120, 130, 140, 100);
                border-radius: 4px;
                font-size: 14px;
                font-weight: 600;
                opacity: 0.70;
            }

            QGroupBox {
                font-weight: 600;
                margin-top: 10px;
                padding-top: 8px;
            }

            QPushButton {
                min-height: 26px;
                padding-left: 10px;
                padding-right: 10px;
            }

            QComboBox {
                min-height: 26px;
                min-width: 105px;
            }

            QTableWidget {
                border: 1px solid rgba(120, 130, 140, 70);
            }
            """)
