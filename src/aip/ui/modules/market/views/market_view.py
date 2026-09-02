from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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

from aip.ui.modules.market.presenters.market_presenter import MarketPresenter
from aip.ui.modules.market.viewmodels.market_view_model import (
    MarketCurveViewData,
    MarketViewModel,
    RelativeValueViewRow,
    RotationViewRow,
)


class _MarketCurveChart(QWidget):
    """Native Qt chart for observed PiPCA points and the official fitted curve."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._curve: MarketCurveViewData | None = None
        self.setMinimumHeight(330)

    def set_curve(self, curve: MarketCurveViewData | None) -> None:
        self._curve = curve
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        curve = self._curve
        if curve is None or not curve.fitted_points:
            painter.setPen(QColor("#718096"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Curva no disponible")
            return

        points = tuple(curve.fitted_points) + tuple(curve.observed_points)
        tenors = [point[0] for point in points]
        yields = [point[1] for point in points]
        min_x, max_x = min(tenors), max(tenors)
        min_y, max_y = min(yields), max(yields)
        x_span = max(max_x - min_x, 0.1)
        y_span = max(max_y - min_y, 0.1)
        min_y -= y_span * 0.10
        max_y += y_span * 0.10
        y_span = max_y - min_y

        left, right, top, bottom = 58.0, 24.0, 22.0, 42.0
        width = max(40.0, self.width() - left - right)
        height = max(40.0, self.height() - top - bottom)

        def map_point(point: tuple[float, float]) -> QPointF:
            x = left + ((point[0] - min_x) / x_span) * width
            y = top + height - ((point[1] - min_y) / y_span) * height
            return QPointF(x, y)

        painter.setPen(QPen(QColor("#D8E1E8"), 1))
        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)
        for index in range(5):
            fraction = index / 4
            y = top + height * fraction
            painter.drawLine(QPointF(left, y), QPointF(left + width, y))
            value = max_y - y_span * fraction
            painter.setPen(QColor("#637587"))
            painter.drawText(QRectF(4, y - 9, left - 10, 18), Qt.AlignmentFlag.AlignRight, f"{value:.2f}%")
            painter.setPen(QPen(QColor("#E1E7EC"), 1))

        painter.setPen(QPen(QColor("#1F5A8A"), 2.2))
        fitted = QPolygonF([map_point(point) for point in curve.fitted_points])
        if len(fitted) >= 2:
            painter.drawPolyline(fitted)

        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.setBrush(QColor("#C9892B"))
        for point in curve.observed_points:
            painter.drawEllipse(map_point(point), 4.0, 4.0)

        painter.setPen(QColor("#53697C"))
        for index in range(6):
            fraction = index / 5
            tenor = min_x + x_span * fraction
            x = left + width * fraction
            painter.drawText(
                QRectF(x - 28, top + height + 8, 56, 20),
                Qt.AlignmentFlag.AlignHCenter,
                f"{tenor:.1f}a",
            )


class MarketView(QWidget):
    """AIP Hybrid market workspace: curves, relative value and rotation screening."""

    def __init__(self, presenter: MarketPresenter | None = None) -> None:
        super().__init__()
        self.setObjectName("marketWorkspace")
        self._presenter = presenter or MarketPresenter()
        self._view_model = self._presenter.build_view_model()
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
        card.setObjectName("marketMetricCard")
        card.setMinimumHeight(76)
        card.setStyleSheet(
            "QFrame#marketMetricCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:8px;} QFrame#marketMetricCard:hover {border-color:#8DB0CB;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        caption = QLabel(title)
        caption.setStyleSheet("color:#667788; font-size:9px; border:none;")
        value = QLabel("-")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        value.setFont(font)
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
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("MERCADO · CURVAS Y VALOR RELATIVO")
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        title.setFont(font)
        subtitle = QLabel("PiPCA · Nelson-Siegel · RV Portafolio · RV Mercado · Rotación")
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
        root.addLayout(header)

        kpis = QGridLayout()
        kpis.setHorizontalSpacing(7)
        definitions = (
            ("curves", "Curvas", "Curvas institucionales cargadas"),
            ("portfolio_rv", "RV Portafolio", "Oportunidades detectadas"),
            ("market_rv", "Universo PiPCA", "Títulos comparados contra curva"),
            ("outside", "Fuera portafolio", "Alternativas del universo de mercado"),
            ("cheap", "Baratos", "Clasificación de RV mercado"),
            ("rich", "Caros", "Clasificación de RV mercado"),
            ("rotation", "Rotación", "Candidatos preliminares"),
            ("spread", "Spread medio", "RV portafolio · puntos base"),
        )
        for index, definition in enumerate(definitions):
            kpis.addWidget(self._metric_card(*definition), index // 4, index % 4)
        root.addLayout(kpis)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabBar::tab {padding:8px 18px; font-weight:600;}"
            "QTabBar::tab:selected {color:#174E78; border-bottom:2px solid #1F5A8A;}"
        )
        root.addWidget(self._tabs, 1)
        self._build_curve_tab()
        self._portfolio_table = self._build_rv_tab("RV Portafolio")
        self._market_table = self._build_rv_tab("RV Mercado")
        self._rotation_table = self._build_rotation_tab()

        self._status = QLabel("")
        self._status.setStyleSheet("color:#617386; padding:3px 2px;")
        root.addWidget(self._status)

    def _build_curve_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Curva:"))
        self._curve_selector = QComboBox()
        self._curve_selector.setMinimumWidth(260)
        self._curve_selector.currentIndexChanged.connect(self._on_curve_changed)
        selector_row.addWidget(self._curve_selector)
        selector_row.addStretch(1)
        self._curve_metrics = QLabel("")
        self._curve_metrics.setStyleSheet("color:#53697C; font-weight:600;")
        selector_row.addWidget(self._curve_metrics)
        layout.addLayout(selector_row)

        group = QGroupBox("Curva de rendimiento · puntos observados vs ajuste oficial")
        group.setStyleSheet(self._group_style())
        group_layout = QVBoxLayout(group)
        self._curve_chart = _MarketCurveChart()
        group_layout.addWidget(self._curve_chart)
        legend = QLabel("● PiPCA observado     ━ Nelson-Siegel")
        legend.setStyleSheet("color:#526577; padding:2px 8px;")
        group_layout.addWidget(legend)
        layout.addWidget(group, 1)
        self._tabs.addTab(page, "Curvas")

    def _new_table(self, headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(list(headers))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(26)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        return table

    def _build_rv_tab(self, title: str) -> QTableWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        table = self._new_table(
            (
                "Serie",
                "Emisor",
                "Moneda",
                "Curva",
                "Plazo",
                "TIR Mercado",
                "TIR Curva",
                "Spread bp",
                "Clasificación",
                "VM / Precio",
                "En portafolio",
            )
        )
        layout.addWidget(table)
        self._tabs.addTab(page, title)
        return table

    def _build_rotation_tab(self) -> QTableWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        note = QLabel(
            "Screening preliminar: compara posiciones del portafolio contra alternativas del universo PiPCA."
        )
        note.setStyleSheet("color:#617386; padding:3px;")
        layout.addWidget(note)
        table = self._new_table(
            (
                "Origen",
                "Emisor origen",
                "Spread origen",
                "Destino",
                "Emisor destino",
                "Spread destino",
                "Pickup bp",
                "Estado",
            )
        )
        layout.addWidget(table)
        self._tabs.addTab(page, "Rotación")
        return table

    @staticmethod
    def _set_item(table: QTableWidget, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        if column >= 4:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table.setItem(row, column, item)

    def _populate_rv_table(
        self,
        table: QTableWidget,
        rows: tuple[RelativeValueViewRow, ...],
        *,
        market_mode: bool,
    ) -> None:
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            exposure = (
                f"{row.market_price:,.4f}"
                if market_mode and row.market_price is not None
                else (
                    f"₡{(row.market_value_crc or 0.0) / 1_000_000:,.2f} MM"
                    if row.market_value_crc is not None
                    else "-"
                )
            )
            in_portfolio = (
                "Sí" if row.in_portfolio is True else "No" if row.in_portfolio is False else "-"
            )
            values = (
                row.series,
                row.issuer,
                row.currency or "-",
                row.curve_id,
                f"{row.tenor:.2f}a",
                f"{row.market_yield:.3f}%",
                f"{row.curve_yield:.3f}%",
                f"{row.spread_bp:+.1f}",
                row.classification,
                exposure,
                in_portfolio,
            )
            for column, value in enumerate(values):
                self._set_item(table, row_index, column, value)
        table.setSortingEnabled(True)

    def _populate_rotation(self, rows: tuple[RotationViewRow, ...]) -> None:
        table = self._rotation_table
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row.source_series,
                row.source_issuer,
                f"{row.source_spread_bp:+.1f}",
                row.target_series,
                row.target_issuer,
                f"{row.target_spread_bp:+.1f}",
                f"{row.spread_pickup_bp:+.1f}",
                row.screening_status,
            )
            for column, value in enumerate(values):
                self._set_item(table, row_index, column, value)
        table.setSortingEnabled(True)

    def _on_curve_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._view_model.curves):
            self._curve_chart.set_curve(None)
            self._curve_metrics.setText("")
            return
        curve = self._view_model.curves[index]
        self._curve_chart.set_curve(curve)
        self._curve_metrics.setText(
            f"{curve.official_model} · Obs {curve.observation_count} · "
            f"RMSE {curve.rmse:.4f} · R² {curve.r_squared:.4f}"
        )

    def refresh(self) -> None:
        self.bind_view_model(self._presenter.refresh())

    def bind_view_model(self, view_model: MarketViewModel) -> None:
        self._view_model = view_model
        summary = view_model.summary
        self._date_label.setText(f"Corte: {getattr(summary, 'market_date', '-')}")
        values = {
            "curves": str(getattr(summary, "curves_loaded", 0)),
            "portfolio_rv": str(getattr(summary, "relative_value_opportunities", 0)),
            "market_rv": str(getattr(summary, "market_relative_value_count", 0)),
            "outside": str(getattr(summary, "market_outside_portfolio_count", 0)),
            "cheap": str(getattr(summary, "market_cheap_count", 0)),
            "rich": str(getattr(summary, "market_rich_count", 0)),
            "rotation": str(getattr(summary, "rotation_candidate_count", 0)),
            "spread": f"{getattr(summary, 'average_spread', '0.00')} bp",
        }
        for key, value in values.items():
            self._kpis[key].setText(value)

        self._curve_selector.blockSignals(True)
        self._curve_selector.clear()
        self._curve_selector.addItems([curve.label for curve in view_model.curves])
        self._curve_selector.blockSignals(False)
        self._on_curve_changed(0 if view_model.curves else -1)

        self._populate_rv_table(
            self._portfolio_table,
            view_model.portfolio_relative_value,
            market_mode=False,
        )
        self._populate_rv_table(
            self._market_table,
            view_model.market_relative_value,
            market_mode=True,
        )
        self._populate_rotation(view_model.rotation_rows)
        self._status.setText(
            getattr(summary, "configuration_message", "")
            or (view_model.error or view_model.status)
        )

    def view_model(self) -> MarketViewModel:
        return self._view_model
