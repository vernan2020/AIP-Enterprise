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
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.treasury.models.treasury_row import TreasuryRow
from aip.ui.modules.treasury.presenters.treasury_presenter import TreasuryPresenter
from aip.ui.modules.treasury.viewmodels.treasury_view_model import TreasuryViewModel
from aip.ui.modules.treasury.widgets.treasury_status_badge import TreasuryStatusBadge


class TreasuryView(QWidget):
    """Treasury decision-support workspace backed by certified liquidity and market outputs."""

    def __init__(self, presenter: TreasuryPresenter | None = None) -> None:
        super().__init__()
        self.setObjectName("treasuryWorkspace")
        self._presenter = presenter or TreasuryPresenter()
        self._view_model = self._presenter.build_view_model()
        self._status_badge = TreasuryStatusBadge("Ready")
        self._kpis: dict[str, QLabel] = {}
        self._build_ui()
        self.bind_view_model(self._view_model)

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D7E0E8; border-radius:8px; margin-top:8px; "
            "font-weight:700; color:#22384C; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )

    def _metric_card(self, key: str, title: str, helper: str) -> QFrame:
        card = QFrame()
        card.setObjectName("treasuryMetricCard")
        card.setMinimumHeight(78)
        card.setStyleSheet(
            "QFrame#treasuryMetricCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:8px;} QFrame#treasuryMetricCard:hover {border-color:#8DB0CB;}"
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self._title = QLabel("TESORERÍA")
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        self._title.setFont(font)
        self._subtitle = QLabel("Liquidez, garantías y oportunidades de mercado")
        self._subtitle.setStyleSheet("color:#667788; font-size:10px;")
        title_box.addWidget(self._title)
        title_box.addWidget(self._subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self._date_label = QLabel("-")
        self._date_label.setStyleSheet(
            "padding:7px 11px; background:#F3F6F9; border:1px solid #D7E0E8; "
            "border-radius:6px; font-weight:600;"
        )
        header.addWidget(self._date_label)
        layout.addLayout(header)

        kpis = QGridLayout()
        kpis.setHorizontalSpacing(7)
        kpis.setVerticalSpacing(7)
        definitions = (
            ("cash", "Posición de caja", "Disponibilidad informada"),
            ("gap", "Brecha liquidez", "Brecha institucional"),
            ("hqla", "HQLA", "Capacidad ajustada"),
            ("mil", "MIL", "Garantía elegible"),
            ("maturity", "Vence ≤30D", "Vencimientos contractuales"),
            ("icl", "ICL Total", "Indicador institucional"),
            ("rotation", "Rotaciones RV", "Candidatos preliminares"),
            ("policy", "Política / Stress", "Estado de motores"),
        )
        for index, definition in enumerate(definitions):
            kpis.addWidget(self._metric_card(*definition), index // 4, index % 4)
        layout.addLayout(kpis)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabBar::tab {padding:8px 18px; font-weight:600;}"
            "QTabBar::tab:selected {color:#174E78; border-bottom:2px solid #1F5A8A;}"
        )
        self._alerts_table = self._build_table_tab("Alertas")
        self._observations_table = self._build_table_tab("Observaciones")
        self._opportunities_table = self._build_table_tab("Oportunidades RV")
        layout.addWidget(self._tabs, 1)

        governance = QGroupBox("Gobierno de la decisión")
        governance.setStyleSheet(self._group_style())
        governance_layout = QVBoxLayout(governance)
        note = QLabel(
            "Tesorería presenta hechos, alertas y oportunidades calculadas por los motores institucionales. "
            "No ejecuta operaciones ni convierte automáticamente una señal analítica en una decisión de inversión."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#617386; padding:6px;")
        governance_layout.addWidget(note)
        layout.addWidget(governance)
        layout.addWidget(self._status_badge)

    def _build_table_tab(self, title: str) -> QTableWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(4, 8, 4, 4)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Señal", "Detalle", "Severidad", "Fuente", "Corte"]
        )
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
        page_layout.addWidget(table)
        self._tabs.addTab(page, title)
        return table

    @staticmethod
    def _populate_table(table: QTableWidget, rows: tuple[TreasuryRow, ...]) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (row.title, row.detail, row.severity, row.source, row.timestamp)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {2, 4}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                table.setItem(row_index, column, item)

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self.bind_view_model(self._view_model)

    def bind_view_model(self, view_model: TreasuryViewModel) -> None:
        self._view_model = view_model
        self._title.setText(view_model.title)
        self._subtitle.setText(view_model.subtitle)
        self._date_label.setText(f"Corte: {view_model.valuation_date}")
        values = {
            "cash": view_model.cash_position,
            "gap": view_model.liquidity_gap,
            "hqla": view_model.hqla_capacity,
            "mil": view_model.mil_capacity,
            "maturity": view_model.maturity_30d,
            "icl": view_model.icl_total,
            "rotation": str(view_model.rotation_candidate_count),
            "policy": f"{view_model.policy_status} / {view_model.stress_status}",
        }
        for key, value in values.items():
            self._kpis[key].setText(value)
        self._populate_table(self._alerts_table, view_model.alerts)
        self._populate_table(self._observations_table, view_model.recommendations)
        self._populate_table(self._opportunities_table, view_model.opportunities)
        self._status_badge.setText(view_model.status)
        self._status_badge.setToolTip(view_model.error or "")

    def view_model(self) -> TreasuryViewModel:
        return self._view_model
