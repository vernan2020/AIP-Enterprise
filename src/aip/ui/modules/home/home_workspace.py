from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory


class HomeWorkspace(QWidget):
    """Pantalla inicial para navegación y contexto operativo de AIP Hybrid."""

    route_requested = Signal(str)

    _MODULES = (
        ("Ejecutivo", "Visión integrada para gestión y ALCO", "executive"),
        ("Portafolio", "Valuación, concentración y oportunidades", "portfolio"),
        ("Mercado", "Curvas PiPCA, valor relativo y rotación", "market"),
        ("Riesgo de Precio", "VeR histórico y sensibilidad DV01", "price_risk"),
        (
            "Inteligencia Macroeconómica",
            "BCCR y escenario institucional aprobado",
            "macro_intelligence",
        ),
        ("Liquidez", "ICL, HQLA, MIL y vencimientos", "liquidity"),
        ("Tesorería", "Alertas, capacidad y oportunidades de valor relativo", "treasury"),
        ("Reportes", "Salida institucional y trazabilidad", "reports"),
    )

    def __init__(self, application_factory: DemoApplicationFactory) -> None:
        super().__init__()
        self.setObjectName("homeWorkspace")
        self._application_factory = application_factory
        self._context_labels: dict[str, QLabel] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 20)
        root.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("homeHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        title_box = QVBoxLayout()
        title = QLabel("AIP HYBRID")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color:#FFFFFF; border:none; background:transparent;")
        subtitle = QLabel("Inteligencia Financiera · Portafolio · ALM · Liquidez · Mercado")
        subtitle.setStyleSheet(
            "color:#DCE9F5; font-size:10px; border:none; background:transparent;"
        )
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        hero_layout.addLayout(title_box)
        hero_layout.addStretch(1)
        self._hero_status = QLabel("SISTEMA LISTO")
        self._hero_status.setStyleSheet(
            "color:#FFFFFF; background:#2B6F9F; border:1px solid #6FA2C6; "
            "border-radius:12px; padding:6px 12px; font-weight:700;"
        )
        hero_layout.addWidget(self._hero_status)
        root.addWidget(hero)

        context = QGridLayout()
        context.setHorizontalSpacing(8)
        context.setVerticalSpacing(8)
        for index, (key, caption) in enumerate(
            (
                ("mode", "Modo"),
                ("cutoff", "Fecha de corte"),
                ("environment", "Entorno"),
                ("sources", "Fuentes"),
            )
        ):
            context.addWidget(self._context_card(key, caption), 0, index)
        root.addLayout(context)

        section = QLabel("ESPACIOS DE TRABAJO")
        section.setStyleSheet("font-size:11px; font-weight:700; color:#526577; padding-top:4px;")
        root.addWidget(section)

        modules = QGridLayout()
        modules.setHorizontalSpacing(10)
        modules.setVerticalSpacing(10)
        for index, (title, detail, route) in enumerate(self._MODULES):
            modules.addWidget(self._module_card(title, detail, route), index // 4, index % 4)
        root.addLayout(modules)
        root.addStretch(1)

        note = QLabel(
            "Los módulos consumen cálculos y datos del entorno institucional de ejecución. La interfaz no sustituye "
            "los motores de dominio ni ejecuta decisiones financieras automáticamente."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#7A8794; font-size:9px; padding:5px 2px;")
        root.addWidget(note)

        self.setStyleSheet(
            "QFrame#homeHero {background:#173F63; border:1px solid #173F63; border-radius:10px;}"
            "QFrame#homeContextCard, QFrame#homeModuleCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:8px;} QFrame#homeModuleCard:hover {border-color:#7FA6C3; background:#F9FBFD;}"
        )

    def _context_card(self, key: str, caption: str) -> QFrame:
        card = QFrame()
        card.setObjectName("homeContextCard")
        card.setMinimumHeight(72)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(11, 8, 11, 8)
        title = QLabel(caption)
        title.setStyleSheet("color:#7A8794; font-size:8px; border:none;")
        value = QLabel("-")
        value.setStyleSheet("color:#17324D; font-size:11px; font-weight:700; border:none;")
        layout.addWidget(title)
        layout.addWidget(value)
        self._context_labels[key] = value
        return card

    def _module_card(self, title: str, detail: str, route: str) -> QFrame:
        card = QFrame()
        card.setObjectName("homeModuleCard")
        card.setMinimumHeight(124)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        name = QLabel(title)
        name.setStyleSheet("font-size:11px; font-weight:700; color:#17324D; border:none;")
        description = QLabel(detail)
        description.setWordWrap(True)
        description.setStyleSheet("font-size:9px; color:#667788; border:none;")
        button = QPushButton("ABRIR")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, value=route: self.route_requested.emit(value))
        button.setStyleSheet(
            "QPushButton {background:#EEF4F8; border:1px solid #C8D9E6; border-radius:5px; "
            "padding:5px 10px; color:#174E78; font-weight:700;}"
            "QPushButton:hover {background:#DCE9F5;}"
        )
        layout.addWidget(name)
        layout.addWidget(description, 1)
        layout.addWidget(button, 0)
        return card

    def refresh(self) -> None:
        config = self._application_factory.config
        mode = str(config.execution_mode).upper()
        cutoff = config.data_cutoff_date.strftime("%d/%m/%Y")
        self._context_labels["mode"].setText("CONFIGURADO" if mode == "CONFIGURED" else mode)
        self._context_labels["cutoff"].setText(cutoff)
        self._context_labels["environment"].setText(
            str(getattr(config, "environment_name", "AIP")).upper()
        )
        try:
            status = self._application_factory.build_system_status()
            source_states = getattr(status, "source_states", {}) or {}
            healthy = sum(
                1
                for state in source_states.values()
                if str(state).upper() in {"HEALTHY", "READY", "AVAILABLE"}
            )
            total = len(source_states)
            self._context_labels["sources"].setText(
                f"{healthy}/{total} operativas" if total else "Entorno compuesto"
            )
            self._hero_status.setText("SISTEMA LISTO")
        except Exception:
            self._context_labels["sources"].setText("Estado disponible en diagnóstico")
            self._hero_status.setText("ENTORNO ACTIVO")
