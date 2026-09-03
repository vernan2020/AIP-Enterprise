from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel
from aip.ui.modules.portfolio.views.portfolio_details_view import PortfolioDetailsView
from aip.ui.modules.portfolio.views.portfolio_positions_view import PortfolioPositionsView
from aip.ui.modules.portfolio.views.portfolio_summary_view import PortfolioSummaryView
from aip.ui.modules.portfolio.views.portfolio_toolbar import PortfolioToolbar
from aip.ui.modules.portfolio.widgets.portfolio_dashboard_chart import PortfolioDashboardBarChart
from aip.ui.modules.portfolio.widgets.portfolio_filter_panel import PortfolioFilterPanel
from aip.ui.modules.portfolio.widgets.portfolio_status_badge import PortfolioStatusBadge


class PortfolioView(QWidget):
    """Panel institucional del portafolio y explorador de posiciones."""

    def __init__(self, presenter: PortfolioPresenter | None = None) -> None:
        super().__init__()
        self.setObjectName("portfolioWorkspace")
        self._presenter = presenter or PortfolioPresenter()
        self._view_model = self._presenter.build_view_model()
        self._toolbar = PortfolioToolbar()
        self._summary = PortfolioSummaryView(self._view_model.summary)
        self._filter_panel = PortfolioFilterPanel()
        self._positions = PortfolioPositionsView(self._view_model.rows)
        self._details = PortfolioDetailsView(
            self._view_model.rows[0] if self._view_model.rows else None
        )
        self._status_bar = PortfolioStatusBadge("Portafolio listo")
        self._content_splitter: QSplitter | None = None
        self._kpis: dict[str, QLabel] = {}
        self._build_ui()
        self._toolbar.actions()[0].triggered.connect(self.refresh)
        self._bind_dashboard(self._view_model)

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D7E0E8; border-radius:8px; margin-top:8px; "
            "font-weight:700; color:#22384C; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )

    @staticmethod
    def _translate_status(value: str) -> str:
        return {
            "ready": "listo",
            "loaded": "cargado",
            "loading": "cargando",
            "error": "error",
            "available": "disponible",
            "unavailable": "no disponible",
        }.get(value.strip().casefold(), value)

    def _metric_card(self, key: str, title: str, helper: str) -> QFrame:
        card = QFrame()
        card.setObjectName("portfolioMetricCard")
        card.setMinimumHeight(78)
        card.setStyleSheet(
            "QFrame#portfolioMetricCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:8px;} QFrame#portfolioMetricCard:hover {border-color:#8DB0CB;}"
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
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(8)
        scroll.setWidget(content)
        root.addWidget(scroll)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("PORTAFOLIO DE INVERSIONES")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        subtitle = QLabel(
            "Valuación · rentabilidad · liquidez · sensibilidad · concentración · valor relativo"
        )
        subtitle.setStyleSheet("color:#667788; font-size:10px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self._date_label = QLabel("-")
        self._date_label.setStyleSheet(
            "padding:7px 11px; background:#F3F6F9; border:1px solid #D7E0E8; "
            "border-radius:6px; font-weight:600;"
        )
        header.addWidget(self._date_label)
        layout.addLayout(header)

        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(7)
        kpi_grid.setVerticalSpacing(7)
        definitions = (
            ("health", "Indicador de Salud", "Pendiente metodología certificada"),
            ("state", "Estado", "Gobierno del panel"),
            ("market_value", "Valor", "Valor de mercado CRC"),
            ("yield", "TIR", "Rendimiento ponderado"),
            ("duration", "Duración", "Duración modificada"),
            ("hqla", "HQLA", "Capacidad líquida elegible"),
            ("dv01", "DV01", "Sensibilidad por 1 pb"),
            ("hhi", "HHI", "Concentración por emisor"),
        )
        for index, definition in enumerate(definitions):
            kpi_grid.addWidget(self._metric_card(*definition), index // 4, index % 4)
        layout.addLayout(kpi_grid)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabBar::tab {padding:8px 18px; font-weight:600;}"
            "QTabBar::tab:selected {color:#174E78; border-bottom:2px solid #1F5A8A;}"
        )
        layout.addWidget(self._tabs, 1)
        self._build_dashboard_tab()
        self._build_positions_tab()

        layout.addWidget(self._status_bar)

    def _build_dashboard_tab(self) -> None:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        issuer_group = QGroupBox("Concentración por emisor · 10 principales")
        issuer_group.setStyleSheet(self._group_style())
        issuer_layout = QVBoxLayout(issuer_group)
        self._issuer_chart = PortfolioDashboardBarChart()
        issuer_layout.addWidget(self._issuer_chart)
        layout.addWidget(issuer_group, 0, 0)

        duration_group = QGroupBox("Distribución por duración")
        duration_group.setStyleSheet(self._group_style())
        duration_layout = QVBoxLayout(duration_group)
        self._duration_chart = PortfolioDashboardBarChart()
        duration_layout.addWidget(self._duration_chart)
        layout.addWidget(duration_group, 0, 1)

        opportunity_group = QGroupBox("Radar de oportunidades · diferencial vs curva")
        opportunity_group.setStyleSheet(self._group_style())
        opportunity_layout = QVBoxLayout(opportunity_group)
        self._opportunity_chart = PortfolioDashboardBarChart(
            value_formatter=lambda value: f"{value:+.1f} pb"
        )
        opportunity_layout.addWidget(self._opportunity_chart)
        layout.addWidget(opportunity_group, 1, 0)

        currency_group = QGroupBox("Asignación por moneda")
        currency_group.setStyleSheet(self._group_style())
        currency_layout = QVBoxLayout(currency_group)
        self._currency_chart = PortfolioDashboardBarChart()
        currency_layout.addWidget(self._currency_chart)
        layout.addWidget(currency_group, 1, 1)

        self._dashboard_note = QLabel("")
        self._dashboard_note.setWordWrap(True)
        self._dashboard_note.setStyleSheet("color:#617386; padding:4px 2px;")
        layout.addWidget(self._dashboard_note, 2, 0, 1, 2)
        self._tabs.addTab(page, "Panel")

    def _build_positions_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(6)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._filter_panel)
        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.addWidget(self._positions)
        self._content_splitter.addWidget(self._details)
        self._content_splitter.setStretchFactor(0, 3)
        self._content_splitter.setStretchFactor(1, 1)
        layout.addWidget(self._content_splitter, 1)
        self._tabs.addTab(page, "Posiciones")

    @staticmethod
    def _market_value_mm(value: str) -> str:
        try:
            amount = Decimal(value.replace(",", ""))
        except Exception:
            return value
        return f"₡{amount / Decimal('1000000'):,.2f} MM"

    def _bind_dashboard(self, view_model: PortfolioViewModel) -> None:
        summary = view_model.summary
        self._date_label.setText(f"Corte: {summary.valuation_date}")
        values = {
            "health": view_model.health_score,
            "state": view_model.health_status,
            "market_value": self._market_value_mm(summary.market_value),
            "yield": summary.weighted_yield,
            "duration": summary.modified_duration,
            "hqla": summary.hqla_percent,
            "dv01": view_model.dv01_total,
            "hhi": view_model.hhi,
        }
        for key, value in values.items():
            self._kpis[key].setText(value)
        self._issuer_chart.set_data(view_model.top_issuer_points)
        self._duration_chart.set_data(view_model.duration_points)
        self._opportunity_chart.set_data(view_model.opportunity_points)
        self._currency_chart.set_data(view_model.currency_points)
        self._dashboard_note.setText(
            f"Calidad de datos: {view_model.data_quality_status} · "
            f"MIL elegible: {summary.mil_eligible_percent} · "
            f"DV01: {self._translate_status(view_model.dv01_status)}. "
            "El Indicador de Salud permanece N/D hasta certificar su metodología institucional."
        )

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self.bind_view_model(self._view_model)

    def bind_view_model(self, view_model: PortfolioViewModel) -> None:
        self._view_model = view_model
        self._bind_dashboard(view_model)

        positions_page = self._tabs.widget(1)
        positions_layout = positions_page.layout() if positions_page is not None else None
        if positions_layout is not None and self._content_splitter is not None:
            positions_layout.removeWidget(self._content_splitter)
            self._content_splitter.hide()

        self._summary = PortfolioSummaryView(view_model.summary)
        self._positions = PortfolioPositionsView(view_model.rows)
        self._details = PortfolioDetailsView(view_model.rows[0] if view_model.rows else None)
        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.addWidget(self._positions)
        self._content_splitter.addWidget(self._details)
        self._content_splitter.setStretchFactor(0, 3)
        self._content_splitter.setStretchFactor(1, 1)
        if positions_layout is not None:
            positions_layout.addWidget(self._content_splitter)

        self._status_bar.setText(self._translate_status(view_model.status))
        self._status_bar.setToolTip(view_model.error or "")

    def view_model(self) -> PortfolioViewModel:
        return self._view_model

    def selected_row(self) -> object | None:
        return self._view_model.rows[0] if self._view_model.rows else None
