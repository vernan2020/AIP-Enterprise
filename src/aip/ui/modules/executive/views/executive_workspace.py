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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.executive.models.executive_row import ExecutiveRow
from aip.ui.modules.executive.presenters.executive_presenter import ExecutivePresenter
from aip.ui.modules.executive.viewmodels.executive_view_model import ExecutiveViewModel
from aip.ui.modules.executive.widgets.executive_signal_radar import ExecutiveSignalRadar
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
        self._kpi_cards: tuple[QFrame, ...] = ()
        self._kpi_grid: QGridLayout | None = None
        self._kpi_columns = 6
        self._context_labels: dict[str, QLabel] = {}
        self._context_cells: tuple[QWidget, ...] = ()
        self._context_grid: QGridLayout | None = None
        self._context_columns = 5
        self._panel_labels: dict[str, QLabel] = {}
        self._domain_grid: QGridLayout | None = None
        self._domain_cards: tuple[QGroupBox, ...] = ()
        self._domain_columns = 2
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
        card.setMinimumHeight(112)
        card.setAccessibleName(title)
        card.setToolTip(f"{title}: {helper}")
        card.setStyleSheet(
            "QFrame#executiveMetricCard {"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #00477F,stop:0.60 #005EB8,stop:1 #00A9E0); "
            "border:1px solid #1675C5; border-radius:12px;"
            "} QFrame#executiveMetricCard:hover {border:1px solid #73B3DD;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 10, 13, 10)
        layout.setSpacing(4)
        caption = QLabel(title)
        caption.setWordWrap(True)
        caption.setStyleSheet("color:#DDF4FF; font-size:10pt; font-weight:600; border:none;")
        value = QLabel("-")
        value_font = QFont()
        value_font.setPointSize(15)
        value_font.setBold(True)
        value.setFont(value_font)
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value.setAccessibleName(f"Valor de {title}")
        value.setStyleSheet("color:#FFFFFF; border:none;")
        hint = QLabel(helper)
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#CBEAF8; font-size:9pt; border:none;")
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
        self._title = QLabel("CENTRO DE INTELIGENCIA EJECUTIVA")
        title_font = QFont()
        title_font.setPointSize(17)
        title_font.setBold(True)
        self._title.setFont(title_font)
        self._subtitle = QLabel(
            "Visión integrada de Portafolio · Liquidez · Mercado · Riesgo · Macroeconomía"
        )
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet("color:#566D7C; font-size:10pt;")
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

        section = QLabel("INDICADORES ESTRATÉGICOS")
        section.setObjectName("executiveSectionTitle")
        section.setStyleSheet(
            "color:#00345F; font-size:10pt; font-weight:800; padding:5px 0 2px 0;"
        )
        root.addWidget(section)

        kpis = QGridLayout()
        kpis.setHorizontalSpacing(7)
        kpis.setVerticalSpacing(7)
        definitions = (
            ("portfolio", "Portafolio", "Valor de mercado CRC"),
            ("yield", "TIR", "Rendimiento ponderado"),
            ("duration", "Duración", "Duración modificada"),
            ("hqla", "HQLA", "Elegibilidad del portafolio"),
            ("gap", "Brecha de Liquidez", "Posición institucional"),
            ("icl", "ICL Total", "Cobertura 30 días"),
        )
        cards: list[QFrame] = []
        for index, definition in enumerate(definitions):
            card = self._metric_card(*definition)
            kpis.addWidget(card, 0, index)
            cards.append(card)
        self._kpi_grid = kpis
        self._kpi_cards = tuple(cards)
        root.addLayout(kpis)

        context_strip = QFrame()
        context_strip.setObjectName("executiveContextStrip")
        context_strip.setStyleSheet(
            "QFrame#executiveContextStrip {background:#F7FAFC; border:1px solid #D7E0E8; "
            "border-radius:9px;}"
        )
        context_layout = QGridLayout(context_strip)
        context_layout.setContentsMargins(10, 6, 10, 6)
        context_layout.setHorizontalSpacing(18)
        context_cells: list[QWidget] = []
        for index, (key, caption) in enumerate(
            (
                ("mil", "MIL elegible"),
                ("rv", "Valor relativo / Rotación"),
                ("quality", "Calidad de datos"),
                ("macro", "Escenario macro"),
                ("horizon", "Horizonte macro"),
            )
        ):
            caption_label = QLabel(caption)
            caption_label.setWordWrap(True)
            caption_label.setStyleSheet("color:#566D7C; font-size:9pt; border:none;")
            value_label = QLabel("-")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_label.setAccessibleName(f"Valor de {caption}")
            value_label.setStyleSheet(
                "color:#00345F; font-size:11pt; font-weight:700; border:none;"
            )
            self._context_labels[key] = value_label
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(1)
            cell_layout.addWidget(caption_label)
            cell_layout.addWidget(value_label)
            context_layout.addWidget(cell, 0, index)
            context_cells.append(cell)
        self._context_grid = context_layout
        self._context_cells = tuple(context_cells)
        root.addWidget(context_strip)

        self._radar = ExecutiveSignalRadar()
        root.addWidget(self._radar)

        panels_heading = QLabel("LECTURA INTEGRADA POR ÁREA")
        panels_heading.setObjectName("executiveSectionTitle")
        panels_heading.setStyleSheet(
            "color:#00345F; font-size:10pt; font-weight:800; padding:7px 0 2px 0;"
        )
        root.addWidget(panels_heading)

        panels = QGridLayout()
        panels.setHorizontalSpacing(8)
        panels.setVerticalSpacing(8)
        domains = (
            self._domain_panel("portfolio_panel", "PORTAFOLIO"),
            self._domain_panel("liquidity_panel", "LIQUIDEZ"),
            self._domain_panel("market_panel", "MERCADO"),
            self._macro_panel(),
        )
        for index, domain_card in enumerate(domains):
            panels.addWidget(domain_card, index // 2, index % 2)
        self._domain_grid = panels
        self._domain_cards = domains
        root.addLayout(panels)

        decisions_heading = QLabel("ALERTAS Y DECISIONES")
        decisions_heading.setObjectName("executiveSectionTitle")
        decisions_heading.setStyleSheet(
            "color:#00345F; font-size:10pt; font-weight:800; padding:7px 0 2px 0;"
        )
        root.addWidget(decisions_heading)
        decisions = QSplitter(Qt.Orientation.Horizontal)
        decisions.setChildrenCollapsible(False)
        decisions.setHandleWidth(7)
        alerts_group = QGroupBox("Alertas y riesgos prioritarios")
        alerts_group.setStyleSheet(self._group_style())
        alerts_layout = QVBoxLayout(alerts_group)
        self._alerts_table = self._decision_table()
        alerts_layout.addWidget(self._alerts_table)
        decisions.addWidget(alerts_group)

        actions_group = QGroupBox("Observaciones y oportunidades")
        actions_group.setStyleSheet(self._group_style())
        actions_layout = QVBoxLayout(actions_group)
        self._recommendations_table = self._decision_table()
        actions_layout.addWidget(self._recommendations_table)
        decisions.addWidget(actions_group)
        decisions.setStretchFactor(0, 1)
        decisions.setStretchFactor(1, 1)
        decisions.setSizes([620, 620])
        self._decision_splitter = decisions
        root.addWidget(decisions)

        root.addWidget(self._status_card)

    @staticmethod
    def _columns_for_width(width: int) -> tuple[int, int, int]:
        if width < 760:
            return 2, 1, 1
        if width < 1220:
            return 3, 3, 2
        return 6, 5, 2

    def _arrange_dashboard(self, width: int) -> None:
        kpi_cols, context_cols, domain_cols = self._columns_for_width(width)
        if self._kpi_grid is not None and kpi_cols != self._kpi_columns:
            for card in self._kpi_cards:
                self._kpi_grid.removeWidget(card)
            for index, card in enumerate(self._kpi_cards):
                self._kpi_grid.addWidget(card, index // kpi_cols, index % kpi_cols)
            for column in range(6):
                self._kpi_grid.setColumnStretch(column, 1 if column < kpi_cols else 0)
            self._kpi_columns = kpi_cols
        if self._context_grid is not None and context_cols != self._context_columns:
            for context_cell in self._context_cells:
                self._context_grid.removeWidget(context_cell)
            for index, context_cell in enumerate(self._context_cells):
                self._context_grid.addWidget(
                    context_cell, index // context_cols, index % context_cols
                )
            self._context_columns = context_cols
        if self._domain_grid is not None and domain_cols != self._domain_columns:
            for domain_card in self._domain_cards:
                self._domain_grid.removeWidget(domain_card)
            for index, domain_card in enumerate(self._domain_cards):
                self._domain_grid.addWidget(
                    domain_card, index // domain_cols, index % domain_cols
                )
            self._domain_columns = domain_cols
        self._decision_splitter.setOrientation(
            Qt.Orientation.Vertical if width < 960 else Qt.Orientation.Horizontal
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._arrange_dashboard(event.size().width())

    def _domain_panel(self, key: str, title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(self._group_style())
        group.setMinimumHeight(185)
        layout = QVBoxLayout(group)
        label = QLabel("-")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet("color:#183247; font-size:10pt; padding:7px;")
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
        self._macro_scenario.setWordWrap(True)
        self._macro_scenario.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._macro_scenario.setStyleSheet("color:#005EB8; font-size:12pt; padding:5px;")
        self._macro_horizon = QLabel("-")
        self._macro_horizon.setStyleSheet("color:#566D7C; font-size:10pt; padding:0 5px;")
        note = QLabel(
            "Escenario institucional aprobado consumido por el entorno de ejecución. El impacto financiero "
            "se incorporará cuando el motor de transmisión publique resultados auditables."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#566D7C; padding:5px; font-size:9pt;")
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
        table.setSortingEnabled(True)
        table.setWordWrap(False)
        table.setToolTip("Seleccione una fila para inspeccionar su señal, severidad y fuente")
        return table

    @classmethod
    def _populate_rows(cls, table: QTableWidget, rows: tuple[ExecutiveRow, ...]) -> None:
        previous_sorting = table.isSortingEnabled()
        table.setSortingEnabled(False)
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
                item.setToolTip(value)
                table.setItem(row_index, column, item)
        table.setSortingEnabled(previous_sorting)

    @staticmethod
    def _lines(values: tuple[str, ...]) -> str:
        return "\n".join(f"• {value}" for value in values)

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self.bind_view_model(self._view_model)

    def bind_view_model(self, view_model: ExecutiveViewModel) -> None:
        self._view_model = view_model
        self._title.setText("CENTRO DE INTELIGENCIA EJECUTIVA")
        self._subtitle.setText(view_model.subtitle)
        self._date_label.setText(f"Corte: {view_model.valuation_date}")
        self._quality_badge.setText(f"Calidad: {view_model.data_quality_status}")
        values = {
            "portfolio": view_model.portfolio_market_value,
            "yield": view_model.weighted_yield,
            "duration": view_model.modified_duration,
            "hqla": view_model.hqla_percent,
            "gap": view_model.liquidity_gap,
            "icl": view_model.icl_total,
        }
        for key, value in values.items():
            self._kpis[key].setText(value)
        self._context_labels["mil"].setText(view_model.mil_percent)
        self._context_labels["rv"].setText(
            f"{view_model.relative_value_count} / {view_model.rotation_candidate_count}"
        )
        self._context_labels["quality"].setText(view_model.data_quality_status)
        self._context_labels["macro"].setText(view_model.macro_scenario)
        self._context_labels["horizon"].setText(view_model.macro_horizon)
        self._panel_labels["portfolio_panel"].setText(self._lines(view_model.portfolio))
        self._panel_labels["liquidity_panel"].setText(self._lines(view_model.liquidity))
        self._panel_labels["market_panel"].setText(self._lines(view_model.market))
        self._macro_scenario.setText(view_model.macro_scenario)
        self._macro_horizon.setText(f"Horizonte: {view_model.macro_horizon}")
        self._radar.set_rows(view_model.alerts, view_model.recommendations)
        self._populate_rows(self._alerts_table, view_model.alerts)
        self._populate_rows(self._recommendations_table, view_model.recommendations)
        self._status_card.setText(self._translate_status(view_model.status))
        self._status_card.setToolTip(view_model.error or "")

    def view_model(self) -> ExecutiveViewModel:
        return self._view_model
