from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from aip.domain.portfolio.services.portfolio_optimization_preflight_service import (
    HistoryReadiness,
    OptimizationPreflightResult,
)
from aip.domain.portfolio.services.portfolio_scenario_risk_service import ScenarioRiskComparison


class PortfolioMarkowitzView(QWidget):
    """Readiness panel; never visualizes or optimizes nonexistent histories.

    A separate, authorized data adapter must supply a validated preflight
    before any frontier is shown. Domain calculations remain outside Qt.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("portfolioMarkowitzView")
        self._cutoff = ""
        self._preflight: OptimizationPreflightResult | None = None
        self._scenario_risk: ScenarioRiskComparison | None = None
        root = QVBoxLayout(self)
        heading = QLabel("Optimización de portafolio — Markowitz")
        heading.setStyleSheet("color:#173B6C; font-size:16px; font-weight:700")
        root.addWidget(heading)
        guidance = QLabel(
            "Media-varianza con rendimientos históricos de retorno total y "
            "restricciones institucionales. Es distinta de la rotación de renta fija "
            "por duración, rendimiento y DV01."
        )
        guidance.setWordWrap(True)
        root.addWidget(guidance)
        group = QGroupBox("Control de disponibilidad y procedencia")
        form = QFormLayout(group)
        self._status = QLabel("MISSING_RETURNS")
        self._status.setObjectName("portfolioMarkowitzStatus")
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._cutoff_label = QLabel("N/D")
        self._asset_count = QLabel("0")
        self._observations = QLabel("0")
        self._frequency = QLabel("N/D")
        self._reason = QLabel(
            "No existe aún una fuente certificada de retornos totales para este corte."
        )
        self._reason.setObjectName("portfolioMarkowitzReason")
        self._reason.setWordWrap(True)
        for label, value in (
            ("Estado de preflight", self._status),
            ("Corte del portafolio", self._cutoff_label),
            ("Instrumentos habilitados", self._asset_count),
            ("Observaciones comunes", self._observations),
            ("Periodos por año", self._frequency),
            ("Diagnóstico", self._reason),
        ):
            form.addRow(label, value)
        root.addWidget(group)
        self._warning = QLabel(
            "Frontera eficiente y cartera óptima NO DISPONIBLES hasta validar "
            "series históricas, moneda, flujo de cupones y política vigente."
        )
        self._warning.setWordWrap(True)
        self._warning.setStyleSheet(
            "color:#894A00; background:#FFF8EB; padding:10px; border-radius:8px;"
        )
        root.addWidget(self._warning)
        risk_group = QGroupBox("Riesgo y cumplimiento — antes / después")
        risk_layout = QVBoxLayout(risk_group)
        self._scenario_risk_status = QLabel("SIN DATOS AUDITADOS")
        self._scenario_risk_status.setObjectName("portfolioScenarioRiskStatus")
        self._scenario_risk_detail = QLabel(
            "No se ha recibido una comparación con duración, DV01, HQLA y APR verificados."
        )
        self._scenario_risk_detail.setObjectName("portfolioScenarioRiskDetail")
        self._scenario_risk_detail.setWordWrap(True)
        self._scenario_risk_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        risk_layout.addWidget(self._scenario_risk_status)
        risk_layout.addWidget(self._scenario_risk_detail)
        root.addWidget(risk_group)
        root.addStretch(1)

    def bind_portfolio_cutoff(self, cutoff: str) -> None:
        """Invalidate stale history evidence when portfolio identity changes."""
        self._cutoff = cutoff
        self._preflight = None
        self._scenario_risk = None
        self._scenario_risk_status.setText("SIN DATOS AUDITADOS")
        self._scenario_risk_detail.setText("Comparación invalidada por nuevo corte del portafolio.")
        self._cutoff_label.setText(cutoff)
        self._status.setText(HistoryReadiness.MISSING_RETURNS.value)
        self._asset_count.setText("0")
        self._observations.setText("0")
        self._frequency.setText("N/D")
        self._reason.setText("Pendiente: series de retornos totales reales y política certificada.")
        self._warning.setText(
            "Frontera eficiente y cartera óptima NO DISPONIBLES sin entradas auditadas."
        )

    def bind_preflight(self, result: OptimizationPreflightResult, *, cutoff: str) -> None:
        if not self._cutoff or cutoff != self._cutoff:
            raise ValueError("Optimization preflight cutoff differs from portfolio")
        self._preflight = result
        self._status.setText(result.status.value)
        self._asset_count.setText(str(len(result.asset_names)))
        self._observations.setText(str(len(result.observation_dates)))
        self._frequency.setText(
            str(result.periods_per_year) if result.periods_per_year is not None else "N/D"
        )
        self._reason.setText(result.reason)
        self._warning.setText(
            "Series verificadas. Falta aprobar los límites de optimización y "
            "ejecutar/certificar el motor sobre estas entradas."
            if result.ready
            else "No se permite optimizar hasta corregir los insumos señalados."
        )

    def bind_risk_comparison(self, result: ScenarioRiskComparison, *, cutoff: str) -> None:
        """Read-only view of externally audited scenario risk; no invented inputs."""
        if (
            not self._cutoff
            or cutoff != self._cutoff
            or result.cutoff.isoformat() != cutoff
        ):
            raise ValueError("Scenario risk cutoff does not match active portfolio")
        self._scenario_risk = result
        self._scenario_risk_status.setText(
            f"Actual: {result.current.status} · Propuesta: {result.proposed.status}"
        )
        self._scenario_risk_detail.setText(
            f"Política: {result.policy_version} · Base CRC {result.portfolio_value_crc:,.2f}\n"
            f"Duración modificada: {result.current.modified_duration_years:.3f} "
            f"→ {result.proposed.modified_duration_years:.3f} años\n"
            f"DV01: {result.current.dv01_crc:,.2f} "
            f"→ {result.proposed.dv01_crc:,.2f} CRC\n"
            f"HQLA: {result.current.hqla_fraction * 100:.2f} "
            f"→ {result.proposed.hqla_fraction * 100:.2f} %\n"
            f"APR crédito: {result.current.credit_rwa_crc:,.2f} "
            f"→ {result.proposed.credit_rwa_crc:,.2f} CRC\n"
            f"Incumplimientos propuesta: {', '.join(result.proposed.breached_limits) or 'Ninguno'}\n"
            f"Límites sin verificar: {', '.join(result.missing_limits) or 'Ninguno'}\n"
            "Diagnóstico parcial; no certifica cumplimiento integral ni ejecuta operaciones."
        )

    @property
    def preflight(self) -> OptimizationPreflightResult | None:
        return self._preflight

    @property
    def scenario_risk(self) -> ScenarioRiskComparison | None:
        return self._scenario_risk
