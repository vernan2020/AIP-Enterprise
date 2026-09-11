from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout


class MarketMetricCard(QFrame):
    """Tarjeta KPI de la generación visual avanzada de Mercado."""

    def __init__(
        self,
        title: str,
        value: str,
        *,
        helper_text: str = "",
        status: str = "",
    ) -> None:
        super().__init__()
        self.setObjectName("marketMetricCard")
        self.setMinimumHeight(88)
        self.setMaximumHeight(104)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._title = str(title)
        self._value = str(value)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        title_label = QLabel(self._title)
        title_label.setObjectName("marketMetricTitle")
        title_font = QFont()
        title_font.setPointSize(8)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header.addWidget(title_label)
        header.addStretch(1)
        self._status_label = QLabel("●")
        self._status_label.setObjectName("marketMetricStatus")
        header.addWidget(self._status_label)
        layout.addLayout(header)

        self._value_label = QLabel(self._value)
        self._value_label.setObjectName("marketMetricValue")
        value_font = QFont()
        value_font.setPointSize(13)
        value_font.setBold(True)
        self._value_label.setFont(value_font)
        self._value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._value_label)

        self._helper_label = QLabel(helper_text or self._default_helper_text(self._title))
        self._helper_label.setObjectName("marketMetricHelper")
        helper_font = QFont()
        helper_font.setPointSize(8)
        self._helper_label.setFont(helper_font)
        self._helper_label.setWordWrap(True)
        layout.addWidget(self._helper_label)

        self.setStyleSheet("""
            QFrame#marketMetricCard {
                background-color: #FFFFFF;
                border: 1px solid #D5DEE3;
                border-radius: 8px;
            }
            QFrame#marketMetricCard:hover {
                background-color: #F0F8FC;
                border-color: #73B3DD;
            }
            QFrame#marketMetricCard QLabel { background: transparent; border: none; }
            QLabel#marketMetricTitle { color: #566D7C; }
            QLabel#marketMetricValue { color: #00345F; }
            QLabel#marketMetricHelper { color: #7B8D98; }
            """)
        self._apply_status(status, self._value)

    def text(self) -> str:
        return self._title

    def value(self) -> str:
        return self._value_label.text()

    def set_value(self, value: str) -> None:
        self._value = str(value)
        self._value_label.setText(self._value)
        self._apply_status("", self._value)

    @staticmethod
    def _default_helper_text(title: str) -> str:
        normalized = str(title).strip().casefold()
        if "fecha de mercado" in normalized:
            return "Fecha del vector de mercado"
        if "curvas" in normalized:
            return "Curvas institucionales disponibles"
        if "fecha de valoración" in normalized:
            return "Fecha de valoración de mercado"
        if "oportunidades" in normalized:
            return "Oportunidades detectadas"
        if "tir" in normalized:
            return "Rendimiento promedio del universo"
        if "duración" in normalized:
            return "Sensibilidad promedio del universo"
        if "diferencial" in normalized:
            return "Diferencial promedio contra curva"
        if "estado" in normalized:
            return "Estado de fuentes y cálculos"
        return "Indicador de mercado"

    def _apply_status(self, status: str, value: str) -> None:
        token = f"{status} {value}".strip().casefold()
        if any(word in token for word in ("error", "fallido", "no disponible")):
            color = "#E4002B"
            tooltip = "Información no disponible"
        elif any(word in token for word in ("degrad", "revisar", "advert")):
            color = "#FF8200"
            tooltip = "Requiere revisión"
        elif any(word in token for word in ("disponible", "cargado", "listo", "configurado")):
            color = "#40C1AC"
            tooltip = "Información disponible"
        else:
            color = "#00A9E0"
            tooltip = "Indicador de mercado"
        self._status_label.setStyleSheet(f"color:{color}; font-weight:700;")
        self._status_label.setToolTip(tooltip)
