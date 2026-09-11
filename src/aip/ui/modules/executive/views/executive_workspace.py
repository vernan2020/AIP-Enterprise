from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.executive.models.executive_row import ExecutiveRow
from aip.ui.modules.executive.presenters.executive_presenter import ExecutivePresenter
from aip.ui.modules.executive.viewmodels.executive_view_model import ExecutiveViewModel
from aip.ui.modules.executive.widgets.executive_status_card import ExecutiveStatusCard


class ExecutiveWorkspace(QWidget):
    """Panel compacto de gestión para el entorno integrado AIP Hybrid."""

    _STATUS_TRANSLATIONS = {
        "ready": "Listo",
        "loaded": "Cargado",
        "loading": "Cargando",
        "available": "Disponible",
        "unavailable": "No disponible",
        "approved": "Aprobado",
        "error": "Error",
    }

    def __init__(self, presenter: ExecutivePresenter | None = None) -> None:
        super().__init__()
        self.setObjectName("executiveWorkspace")
        self._presenter = presenter or ExecutivePresenter()
        self._view_model = self._presenter.build_view_model()
        self._status_card = ExecutiveStatusCard("Listo")
        self._kpis: dict[str, QLabel] = {}
        self._panel_labels: dict[str, QLabel] = {}
        self._build_ui()
        self.bind_view_model(self._view_model)

    @classmethod
    def _translate_status(cls, value: str) -> str:
        return cls._STATUS_TRANSLATIONS.get(value.strip().casefold(), value)

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D7E0E8; border-radius:8px; margin-top:8px; "
            "font-weight:700; color:#22384C; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )

    def _metric_card(self, key: str, title: str, helper: str) -> QFrame:
        card = QFrame()
        card.setObjectName("executiveMetricCard")
        card.setMinimumHeight(78)
        card.setStyleSheet(
            "QFrame#executiveMetricCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:8px;} QFrame#executiveMetricCard:hover {border-color:#8DB0CB;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        caption = QLabel(title)
        caption.setStyleSheet("color:#667788; font-size:9px; border:none;")
        value = QLabel("-")
        value_font = QFont()
        value_font.setPointSize(12)
        value_font.setBold(True)
        value.setFont(value_font)
        value.setStyleSheet("color:#142E46; border:none;")
        hint = QLabel(helper)
        hint.setStyleSheet("color:#8A98A6; font-size:8px; border:none;")
        layout.addWidget(caption)
        layout.addWidget(value)
        layout.addWidget(hint)
        self._kpis[key] = value
        return card

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(8)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self._title = QLabel("PANEL EJECUTIVO")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self._title.setFont(title_font)
        self._subtitle = QLabel("Portafolio · Liquidez · Mercado · Inteligencia Macroeconómica")
        self._subtitle.setStyleSheet("color:#667788; font-size:10px;")
        title_box.addWidget(self._title)
        title_box.addWidget(self._subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self._quality_badge = QLabel("Calidad: -")
        self._quality_badge.setStyleSheet(
            "padding:7px 10px; background:#F3F6F9; border:1px solid #D7E0E8; "
            "border-radius:6px; color:#526577; font-weight:600;"
        )
        self._date_label = QLabel("-")
        self._date_label.setStyleSheet(
            "padding:7px 10px; background:#EEF4F8; border:1px solid #C8D9E6; "
            "border-radius:6px; color:#174E78; font-weight:700;"
        )
        header.addWidget(self._quality_badge)
        header.addWidget(self._date_label)
        root.addLayout(header)

        kpis = QGridLayout()
        kpis.setHorizontalSpacing(7)
        kpis.setVerticalSpacing(7)
        definitions = (
            ("portfolio", "Portafolio", "Valor de mercado CRC"),
            ("yield", "TIR", "Rendimiento ponderado"),
            ("duration", "Duración", "Duración modificada"),
            ("hqla", "HQLA", "Elegibilidad del portafolio"),
            ("mil", "MIL", "Elegibilidad de garantía"),
            ("gap", "Brecha de Liquidez", "Posición institucional"),
            ("icl", "ICL Total", "Cobertura 30 días"),
            ("rv", "Valor Relativo / Rotación", "Universo de mercado y candidatos"),
        )
        for index, definition in enumerate(definitions):
            kpis.addWidget(self._metric_card(*definition), index // 4, index % 4)
        root.addLayout(kpis)

        panels = QGridLayout()
        panels.setHorizontalSpacing(8)
        panels.setVerticalSpacing(8)
        panels.addWidget(self._domain_panel("portfolio_panel", "PORTAFOLIO"), 0, 0)
        panels.addWidget(self._domain_panel("liquidity_panel", "LIQUIDEZ"), 0, 1)
        panels.addWidget(self._domain_panel("market_panel", "MERCADO"), 1, 0)
        panels.addWidget(self._macro_panel(), 1, 1)
        root.addLayout(panels)

        decisions = QHBoxLayout()
        decisions.setSpacing(8)
        alerts_group = QGroupBox("Alertas")
        alerts_group.setStyleSheet(self._group_style())
        alerts_layout = QVBoxLayout(alerts_group)
        self._alerts_table = self._decision_table()
        alerts_layout.addWidget(self._alerts_table)
        decisions.addWidget(alerts_group, 1)

        actions_group = QGroupBox("Observaciones y oportunidades")
        actions_group.setStyleSheet(self._group_style())
        actions_layout = QVBoxLayout(actions_group)
        self._recommendations_table = self._decision_table()
        actions_layout.addWidget(self._recommendations_table)
        decisions.addWidget(actions_group, 1)
        root.addLayout(decisions)

        root.addWidget(self._status_card)

    def _domain_panel(self, key: str, title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(self._group_style())
        group.setMinimumHeight(160)
        layout = QVBoxLayout(group)
        label = QLabel("-")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setStyleSheet("color:#44586B; line-height:1.3; padding:5px;")
        layout.addWidget(label)
        self._panel_labels[key] = label
        return group

    def _macro_panel(self) -> QGroupBox:
        group = QGroupBox("INTELIGENCIA MACROECONÓMICA")
        group.setStyleSheet(self._group_style())
        group.setMinimumHeight(160)
        layout = QVBoxLayout(group)
        self._macro_scenario = QLabel("-")
        macro_font = QFont()
        macro_font.setPointSize(12)
        macro_font.setBold(True)
        self._macro_scenario.setFont(macro_font)
        self._macro_scenario.setStyleSheet("color:#174E78; padding:5px;")
        self._macro_horizon = QLabel("-")
        self._macro_horizon.setStyleSheet("color:#667788; padding:0 5px;")
        note = QLabel(
            "Escenario institucional aprobado consumido por el entorno de ejecución. El impacto financiero "
            "se incorporará cuando el motor de transmisión publique resultados auditables."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#7A8794; padding:5px; font-size:9px;")
        layout.addWidget(self._macro_scenario)
        layout.addWidget(self._macro_horizon)
        layout.addWidget(note)
        layout.addStretch(1)
        return group

    @staticmethod
    def _decision_table() -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Señal", "Detalle", "Categoría", "Severidad", "Fuente"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(30)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.setMinimumHeight(210)
        return table

    @classmethod
    def _populate_rows(cls, table: QTableWidget, rows: tuple[ExecutiveRow, ...]) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row.title,
                row.detail,
                row.category,
                cls._translate_status(row.severity),
                row.source,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {2, 3}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                table.setItem(row_index, column, item)

    @staticmethod
    def _lines(values: tuple[str, ...]) -> str:
        return "\n".join(f"• {value}" for value in values)

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self.bind_view_model(self._view_model)

    def bind_view_model(self, view_model: ExecutiveViewModel) -> None:
        self._view_model = view_model
        self._title.setText(view_model.title)
        self._subtitle.setText(view_model.subtitle)
        self._date_label.setText(f"Corte: {view_model.valuation_date}")
        self._quality_badge.setText(f"Calidad: {view_model.data_quality_status}")
        values = {
            "portfolio": view_model.portfolio_market_value,
            "yield": view_model.weighted_yield,
            "duration": view_model.modified_duration,
            "hqla": view_model.hqla_percent,
            "mil": view_model.mil_percent,
            "gap": view_model.liquidity_gap,
            "icl": view_model.icl_total,
            "rv": f"{view_model.relative_value_count} / {view_model.rotation_candidate_count}",
        }
        for key, value in values.items():
            self._kpis[key].setText(value)
        self._panel_labels["portfolio_panel"].setText(self._lines(view_model.portfolio))
        self._panel_labels["liquidity_panel"].setText(self._lines(view_model.liquidity))
        self._panel_labels["market_panel"].setText(self._lines(view_model.market))
        self._macro_scenario.setText(view_model.macro_scenario)
        self._macro_horizon.setText(f"Horizonte: {view_model.macro_horizon}")
        self._populate_rows(self._alerts_table, view_model.alerts)
        self._populate_rows(self._recommendations_table, view_model.recommendations)
        self._status_card.setText(self._translate_status(view_model.status))
        self._status_card.setToolTip(view_model.error or "")

    def view_model(self) -> ExecutiveViewModel:
        return self._view_model
