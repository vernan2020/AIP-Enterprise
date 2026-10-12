from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aip.domain.portfolio.services.capital_equivalent_rate_service import (
    CapitalEquivalentRateInput,
    CapitalEquivalentRateService,
)
from aip.domain.portfolio.services.portfolio_capital_consumption_service import ExposureClass


class CapitalEquivalentRateView(QWidget):
    """Standalone scenario calculator; requires explicit editable equity hurdle."""

    _CLASSIFICATIONS = (
        ("Gobierno CRC · 0%", ExposureClass.GOVERNMENT_CRC),
        ("BCCR CRC · 0%", ExposureClass.BCCR_CRC),
        ("Gobierno USD · 75%", ExposureClass.GOVERNMENT_USD),
        ("BCCR USD · 75%", ExposureClass.BCCR_USD),
        ("Calificación categoría 4 · 75%", ExposureClass.RATED_4),
        ("Calificación categoría 5 · 90%", ExposureClass.RATED_5),
        ("Sin calificación · 100%", ExposureClass.UNRATED),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Tasa equivalente ajustada por costo de capital")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#173B6C;")
        layout.addWidget(title)
        guidance = QLabel(
            "Simulación económica, no indicador regulatorio oficial. "
            "Ingrese importes en CRC y tasas anuales en porcentajes."
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)

        parameters = QGroupBox("Parámetros del escenario")
        form = QFormLayout(parameters)
        self._invested = QLineEdit()
        self._invested.setPlaceholderText("Monto invertido CRC")
        form.addRow("Monto invertido CRC", self._invested)
        self._exposure = QLineEdit()
        self._exposure.setPlaceholderText("Exposición regulatoria CRC verificada")
        form.addRow("Exposición regulatoria CRC", self._exposure)
        self._yield = QLineEdit()
        self._yield.setPlaceholderText("Ej.: 8.5")
        form.addRow("Rendimiento anual neto (%)", self._yield)
        self._equity_cost = QLineEdit()
        self._equity_cost.setObjectName("portfolioEditableEquityCost")
        self._equity_cost.setPlaceholderText("Editable; no se presupone una tasa")
        form.addRow("Costo anual del patrimonio (%)", self._equity_cost)
        self._target = QLabel("16,00 %")
        form.addRow("Suficiencia patrimonial objetivo", self._target)
        self._classification = QComboBox()
        for label, exposure_class in self._CLASSIFICATIONS:
            self._classification.addItem(label, exposure_class)
        form.addRow("Clasificación para el escenario", self._classification)
        layout.addWidget(parameters)

        self._calculate = QPushButton("Calcular tasa equivalente")
        self._calculate.clicked.connect(self._calculate_equivalent)
        layout.addWidget(self._calculate)
        self._result = QLabel("Ingrese los parámetros; no se utilizan tasas supuestas.")
        self._result.setObjectName("portfolioCapitalEquivalentResult")
        self._result.setWordWrap(True)
        self._result.setTextInteractionFlags(
            self._result.textInteractionFlags()
        )
        layout.addWidget(self._result)
        layout.addStretch(1)

    @staticmethod
    def _decimal(text: str, label: str) -> Decimal:
        value = text.strip().replace(",", ".")
        if not value:
            raise ValueError(f"Debe completar: {label}")
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"Valor inválido: {label}") from exc
        if not parsed.is_finite():
            raise ValueError(f"Valor no finito: {label}")
        return parsed

    def _calculate_equivalent(self) -> None:
        try:
            item = CapitalEquivalentRateInput(
                invested_amount_crc=self._decimal(self._invested.text(), "monto invertido"),
                regulatory_exposure_crc=self._decimal(
                    self._exposure.text(), "exposición regulatoria"
                ),
                annual_net_yield=self._decimal(self._yield.text(), "rendimiento") / 100,
                annual_cost_of_equity=self._decimal(
                    self._equity_cost.text(), "costo anual del patrimonio"
                )
                / 100,
                exposure_class=self._classification.currentData(),
            )
            result = CapitalEquivalentRateService.calculate(item)
        except (ValueError, TypeError) as exc:
            self._result.setText(str(exc))
            return

        self._result.setText(
            f"APR de crédito ponderado: {item.regulatory_exposure_crc * result.risk_weight:,.2f} CRC\n"
            f"Capital objetivo asignado: {result.required_capital_crc:,.2f} CRC\n"
            f"Costo anual del patrimonio imputado: {result.annual_equity_charge_crc:,.2f} CRC\n"
            f"Tasa equivalente respecto a Gobierno CRC (0%): "
            f"{result.equivalent_yield_at_reference_risk_weight * 100:,.4f} %\n"
            "Cálculo de escenario; sujeto a confirmación normativa de cada título."
        )
