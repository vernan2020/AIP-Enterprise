from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.price_risk.models.price_risk_simulation import (
    PriceRiskSimulationRequestTrade,
    PriceRiskSimulationSecurityOption,
    PriceRiskSimulationViewModel,
)
from aip.ui.modules.price_risk.presenters.price_risk_presenter import PriceRiskPresenter
from aip.ui.modules.price_risk.widgets.risk_charts import RiskBarChartWidget


class _SimulationWorker(QObject):
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, presenter: PriceRiskPresenter) -> None:
        super().__init__()
        self._presenter = presenter

    @Slot(object)
    def calculate(self, requests: object) -> None:
        try:
            if not isinstance(requests, tuple):
                raise TypeError("El escenario de simulación no tiene un formato válido")
            self.result_ready.emit(self._presenter.simulate(requests))
        except Exception as exc:
            self.failed.emit(str(exc))


class PortfolioVaRSimulatorView(QWidget):
    """Passive what-if UI for purchases, sales and mixed VeR scenarios."""

    simulation_requested = Signal(object)

    def __init__(self, presenter: PriceRiskPresenter) -> None:
        super().__init__()
        self.setObjectName("portfolioVaRSimulator")
        self._presenter = presenter
        self._securities: tuple[PriceRiskSimulationSecurityOption, ...] = ()
        self._scenario: list[PriceRiskSimulationRequestTrade] = []
        self._busy = False
        self._closing = False
        self._result_labels: dict[str, QLabel] = {}
        self._build_ui()
        self._setup_worker()

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D5DEE3; border-radius:8px; margin-top:8px; "
            "font-weight:700; color:#005EB8; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(3, 6, 3, 3)
        root.setSpacing(8)

        notice = QFrame()
        notice.setObjectName("simulationNotice")
        notice.setStyleSheet(
            "QFrame#simulationNotice {background:#F0F8FC; border:1px solid #73B3DD; "
            "border-radius:8px;}"
        )
        notice_layout = QVBoxLayout(notice)
        notice_layout.setContentsMargins(12, 8, 12, 8)
        title = QLabel("SIMULADOR DE CAMBIOS EN EL PORTAFOLIO")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color:#00345F;")
        description = QLabel(
            "Modele compras, ventas o ambas. El escenario se mantiene en memoria y no modifica "
            "el portafolio real. El VeR simulado usa exactamente la metodología institucional: "
            "521 precios, horizonte 21 observaciones y 500 escenarios históricos."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#566D7C; font-size:9px;")
        notice_layout.addWidget(title)
        notice_layout.addWidget(description)
        root.addWidget(notice)

        builder = QGroupBox("Construcción del escenario")
        builder.setStyleSheet(self._group_style())
        builder_layout = QGridLayout(builder)
        builder_layout.setHorizontalSpacing(8)
        builder_layout.setVerticalSpacing(6)

        builder_layout.addWidget(QLabel("Operación"), 0, 0)
        self._action = QComboBox()
        self._action.addItem("Compra", "BUY")
        self._action.addItem("Venta", "SELL")
        self._action.currentIndexChanged.connect(self._rebuild_security_combo)
        builder_layout.addWidget(self._action, 1, 0)

        builder_layout.addWidget(QLabel("Título"), 0, 1)
        self._security = QComboBox()
        self._security.setEditable(True)
        self._security.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._security.setMinimumWidth(420)
        self._security.currentIndexChanged.connect(self._show_selected_security)
        builder_layout.addWidget(self._security, 1, 1)

        builder_layout.addWidget(QLabel("Monto VM CRC equivalente (₡ MM)"), 0, 2)
        self._amount = QDoubleSpinBox()
        self._amount.setDecimals(2)
        self._amount.setMinimum(0.01)
        self._amount.setMaximum(999_999_999.99)
        self._amount.setSingleStep(100.00)
        self._amount.setGroupSeparatorShown(True)
        builder_layout.addWidget(self._amount, 1, 2)

        self._add_button = QPushButton("Agregar operación")
        self._add_button.clicked.connect(self._add_trade)
        builder_layout.addWidget(self._add_button, 1, 3)

        self._security_detail = QLabel("Seleccione un título.")
        self._security_detail.setWordWrap(True)
        self._security_detail.setStyleSheet("color:#566D7C; font-size:8px;")
        builder_layout.addWidget(self._security_detail, 2, 0, 1, 4)
        builder_layout.setColumnStretch(1, 1)
        root.addWidget(builder)

        scenario_group = QGroupBox("Operaciones hipotéticas")
        scenario_group.setStyleSheet(self._group_style())
        scenario_layout = QVBoxLayout(scenario_group)
        self._scenario_table = QTableWidget(0, 6)
        self._scenario_table.setHorizontalHeaderLabels(
            ("Operación", "Serie", "Emisor", "Moneda", "Monto VM", "Origen")
        )
        self._scenario_table.verticalHeader().setVisible(False)
        self._scenario_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._scenario_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._scenario_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._scenario_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._scenario_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._scenario_table.setMaximumHeight(190)
        scenario_layout.addWidget(self._scenario_table)

        actions = QHBoxLayout()
        self._remove_button = QPushButton("Eliminar seleccionada")
        self._remove_button.clicked.connect(self._remove_selected_trade)
        self._clear_button = QPushButton("Limpiar escenario")
        self._clear_button.clicked.connect(self.clear_scenario)
        actions.addWidget(self._remove_button)
        actions.addWidget(self._clear_button)
        actions.addStretch(1)
        self._calculate_button = QPushButton("Calcular VeR simulado")
        self._calculate_button.setStyleSheet(
            "QPushButton {background:#005EB8; color:white; border:none; border-radius:6px; "
            "padding:8px 16px; font-weight:700;}"
            "QPushButton:disabled {background:#A9BAC5;}"
        )
        self._calculate_button.clicked.connect(self._calculate)
        actions.addWidget(self._calculate_button)
        scenario_layout.addLayout(actions)
        root.addWidget(scenario_group)

        result_group = QGroupBox("Impacto sobre el VeR")
        result_group.setStyleSheet(self._group_style())
        result_layout = QVBoxLayout(result_group)

        kpis = QGridLayout()
        definitions = (
            ("base_var", "VeR actual"),
            ("simulated_var", "VeR simulado"),
            ("delta_var", "Δ VeR"),
            ("relative_var", "Variación VeR"),
            ("base_percent", "VeR % actual"),
            ("simulated_percent", "VeR % simulado"),
            ("delta_pp", "Δ VeR p.p."),
            ("delta_vm", "Δ exposición VeR"),
        )
        for index, (key, caption) in enumerate(definitions):
            card = self._result_card(key, caption)
            kpis.addWidget(card, index // 4, index % 4)
        result_layout.addLayout(kpis)

        comparison = QGroupBox("VeR actual vs. VeR simulado")
        comparison.setStyleSheet(self._group_style())
        comparison_layout = QVBoxLayout(comparison)
        self._comparison_chart = RiskBarChartWidget(
            value_formatter=lambda value: f"₡{value / Decimal('1000000'):,.2f} MM"
        )
        comparison_layout.addWidget(self._comparison_chart)
        result_layout.addWidget(comparison)

        self._result_detail = QLabel("Construya un escenario y presione “Calcular VeR simulado”.")
        self._result_detail.setWordWrap(True)
        self._result_detail.setStyleSheet("color:#566D7C; padding:5px;")
        result_layout.addWidget(self._result_detail)
        root.addWidget(result_group)

        self._status = QLabel("Escenario listo para configurar.")
        self._status.setStyleSheet("color:#566D7C; font-weight:600;")
        root.addWidget(self._status)
        self._update_controls()

    def _result_card(self, key: str, caption: str) -> QFrame:
        card = QFrame()
        card.setObjectName("simulationMetricCard")
        card.setMinimumHeight(64)
        card.setStyleSheet(
            "QFrame#simulationMetricCard {background:#FFFFFF; border:1px solid #D5DEE3; "
            "border-radius:7px;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(9, 6, 9, 6)
        label = QLabel(caption)
        label.setStyleSheet("color:#566D7C; font-size:8px; border:none;")
        value = QLabel("-")
        value.setStyleSheet("color:#00345F; font-weight:700; font-size:11px; border:none;")
        layout.addWidget(label)
        layout.addWidget(value)
        self._result_labels[key] = value
        return card

    def _setup_worker(self) -> None:
        self._thread = QThread(self)
        self._thread.setObjectName("portfolioVaRSimulationWorkerThread")
        self._worker = _SimulationWorker(self._presenter)
        self._worker.moveToThread(self._thread)
        self.simulation_requested.connect(
            self._worker.calculate,
            Qt.ConnectionType.QueuedConnection,
        )
        self._worker.result_ready.connect(
            self._on_simulation_ready,
            Qt.ConnectionType.QueuedConnection,
        )
        self._worker.failed.connect(
            self._on_simulation_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def bind_securities(
        self,
        securities: tuple[PriceRiskSimulationSecurityOption, ...],
    ) -> None:
        self._securities = securities
        self.clear_scenario(reset_result=True)
        self._rebuild_security_combo()

    @Slot(int)
    def _rebuild_security_combo(self, _index: int = -1) -> None:
        selected_key = self._security.currentData() if self._security.count() else None
        action = str(self._action.currentData() or "BUY")
        options = (
            self._securities
            if action == "BUY"
            else tuple(item for item in self._securities if item.in_portfolio)
        )
        self._security.blockSignals(True)
        self._security.clear()
        for item in options:
            self._security.addItem(item.display_text, item.security_key)
        if selected_key:
            index = self._security.findData(selected_key)
            if index >= 0:
                self._security.setCurrentIndex(index)
        self._security.blockSignals(False)
        self._show_selected_security()
        self._update_controls()

    @Slot(int)
    def _show_selected_security(self, _index: int = -1) -> None:
        option = self._selected_option()
        if option is None:
            self._security_detail.setText(
                "No hay títulos disponibles para la operación seleccionada."
            )
            return
        self._security_detail.setText(
            f"{option.series} · {option.issuer} · {option.currency} · {option.source} · "
            f"VM actual: {option.current_market_value} · Precio: {option.market_price} · "
            f"Rendimiento: {option.market_yield}"
        )

    def _selected_option(self) -> PriceRiskSimulationSecurityOption | None:
        key = self._security.currentData()
        if not key:
            return None
        return next((item for item in self._securities if item.security_key == key), None)

    @Slot(bool)
    def _add_trade(self, _checked: bool = False) -> None:
        option = self._selected_option()
        if option is None:
            QMessageBox.warning(self, "Simulador VeR", "Seleccione un título válido.")
            return
        amount_mm = Decimal(str(self._amount.value()))
        if amount_mm <= 0:
            QMessageBox.warning(self, "Simulador VeR", "Ingrese un monto mayor que cero.")
            return
        request = PriceRiskSimulationRequestTrade(
            action=str(self._action.currentData() or "BUY"),
            security_key=option.security_key,
            market_value_crc=amount_mm * Decimal("1000000"),
        )
        self._scenario.append(request)
        self._append_scenario_row(request, option)
        self._status.setText(
            f"Escenario con {len(self._scenario)} operación(es). Pendiente de recálculo."
        )
        self._clear_result()
        self._update_controls()

    def _append_scenario_row(
        self,
        request: PriceRiskSimulationRequestTrade,
        option: PriceRiskSimulationSecurityOption,
    ) -> None:
        row = self._scenario_table.rowCount()
        self._scenario_table.insertRow(row)
        values = (
            "Compra" if request.action == "BUY" else "Venta",
            option.series,
            option.issuer,
            option.currency,
            f"₡{request.market_value_crc / Decimal('1000000'):,.2f} MM",
            option.source,
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 4:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._scenario_table.setItem(row, column, item)

    @Slot(bool)
    def _remove_selected_trade(self, _checked: bool = False) -> None:
        row = self._scenario_table.currentRow()
        if row < 0 or row >= len(self._scenario):
            return
        self._scenario.pop(row)
        self._scenario_table.removeRow(row)
        self._clear_result()
        self._status.setText(
            f"Escenario con {len(self._scenario)} operación(es). Pendiente de recálculo."
        )
        self._update_controls()

    @Slot(bool)
    def clear_scenario(
        self,
        _checked: bool = False,
        *,
        reset_result: bool = True,
    ) -> None:
        self._scenario.clear()
        self._scenario_table.setRowCount(0)
        if reset_result:
            self._clear_result()
        self._status.setText("Escenario listo para configurar.")
        self._update_controls()

    def _clear_result(self) -> None:
        for label in self._result_labels.values():
            label.setText("-")
            label.setStyleSheet("color:#00345F; font-weight:700; font-size:11px; border:none;")
        self._comparison_chart.set_data(())
        self._result_detail.setText("Construya un escenario y presione “Calcular VeR simulado”.")

    @Slot(bool)
    def _calculate(self, _checked: bool = False) -> None:
        if self._busy or not self._scenario:
            return
        self._busy = True
        self._status.setText("Recalculando 500 escenarios históricos para el portafolio simulado…")
        self._status.setStyleSheet("color:#005EB8; font-weight:700;")
        self._update_controls()
        self.simulation_requested.emit(tuple(self._scenario))

    @Slot(object)
    def _on_simulation_ready(self, payload: object) -> None:
        if self._closing:
            return
        self._busy = False
        if not isinstance(payload, PriceRiskSimulationViewModel):
            self._on_simulation_failed("El simulador devolvió un resultado no válido")
            return
        self._bind_result(payload)
        self._update_controls()

    @Slot(str)
    def _on_simulation_failed(self, message: str) -> None:
        if self._closing:
            return
        self._busy = False
        self._status.setText(f"No fue posible calcular el escenario: {message}")
        self._status.setStyleSheet("color:#E4002B; font-weight:700;")
        self._update_controls()

    def _bind_result(self, result: PriceRiskSimulationViewModel) -> None:
        values = {
            "base_var": result.base_var,
            "simulated_var": result.simulated_var,
            "delta_var": result.delta_var,
            "relative_var": result.relative_var_change,
            "base_percent": result.base_var_percent,
            "simulated_percent": result.simulated_var_percent,
            "delta_pp": result.delta_var_percent_points,
            "delta_vm": result.delta_market_value,
        }
        for key, value in values.items():
            self._result_labels[key].setText(value)

        delta_text = result.delta_var.strip()
        delta_color = "#E4002B" if delta_text.startswith("+") else "#167A68"
        self._result_labels["delta_var"].setStyleSheet(
            f"color:{delta_color}; font-weight:800; font-size:11px; border:none;"
        )
        self._result_labels["relative_var"].setStyleSheet(
            f"color:{delta_color}; font-weight:800; font-size:11px; border:none;"
        )
        self._comparison_chart.set_data(result.comparison_points)

        details = [
            f"Corte {result.valuation_date}. Escenario VeR actual {result.base_scenario}; "
            f"escenario simulado {result.simulated_scenario}.",
            f"Exposición actual {result.base_market_value}; simulada {result.simulated_market_value}.",
        ]
        if result.warnings:
            details.append("Advertencias: " + " · ".join(result.warnings))
        if result.notes:
            details.append("Notas: " + " · ".join(result.notes))
        self._result_detail.setText("\n".join(details))

        if result.status == "CALCULATED":
            self._status.setText("VeR simulado calculado con la metodología institucional.")
            self._status.setStyleSheet("color:#167A68; font-weight:700;")
        elif result.status == "CALCULATED_WITH_WARNINGS":
            self._status.setText(
                "VeR simulado calculado con advertencias de cobertura o elegibilidad."
            )
            self._status.setStyleSheet("color:#A95B00; font-weight:700;")
        else:
            self._status.setText("El VeR simulado no pudo quedar disponible para este escenario.")
            self._status.setStyleSheet("color:#E4002B; font-weight:700;")

    def _update_controls(self) -> None:
        has_security = self._security.count() > 0
        self._add_button.setEnabled(has_security and not self._busy)
        self._remove_button.setEnabled(bool(self._scenario) and not self._busy)
        self._clear_button.setEnabled(bool(self._scenario) and not self._busy)
        self._calculate_button.setEnabled(bool(self._scenario) and not self._busy)
        self._action.setEnabled(not self._busy)
        self._security.setEnabled(not self._busy)
        self._amount.setEnabled(not self._busy)

    def shutdown(self) -> None:
        self._closing = True
        thread = getattr(self, "_thread", None)
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            thread.quit()
            thread.wait(30000)

    @property
    def scenario_count(self) -> int:
        return len(self._scenario)
