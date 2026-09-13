from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QSplitter,
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
from aip.ui.modules.market.views.market_summary_view import MarketSummaryView
from aip.ui.modules.market.views.relative_value_view import RelativeValueView


class _MarketCurveChart(QWidget):
    """Curva institucional nativa: PiPCA observado, Nelson-Siegel y selección RV."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._curve: MarketCurveViewData | None = None
        self._highlight: RelativeValueViewRow | None = None
        self.setMinimumHeight(330)

    def set_curve(
        self,
        curve: MarketCurveViewData | None,
        highlight: RelativeValueViewRow | None = None,
    ) -> None:
        self._curve = curve
        self._highlight = highlight
        self.update()

    def set_highlight(self, row: RelativeValueViewRow | None) -> None:
        self._highlight = row
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        curve = self._curve
        if curve is None or not curve.fitted_points:
            painter.setPen(QColor("#7B8D98"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Curva no disponible",
            )
            return

        points = tuple(curve.fitted_points) + tuple(curve.observed_points)
        highlight = self._highlight
        if highlight is not None and highlight.curve_id == curve.curve_id:
            points += ((highlight.tenor, highlight.market_yield),)

        tenors = [point[0] for point in points]
        yields = [point[1] for point in points]
        min_x, max_x = min(tenors), max(tenors)
        min_y, max_y = min(yields), max(yields)
        x_span = max(max_x - min_x, 0.1)
        y_span = max(max_y - min_y, 0.1)
        min_y -= y_span * 0.12
        max_y += y_span * 0.12
        y_span = max(max_y - min_y, 0.1)

        left, right, top, bottom = 58.0, 24.0, 24.0, 42.0
        width = max(40.0, self.width() - left - right)
        height = max(40.0, self.height() - top - bottom)

        def map_point(point: tuple[float, float]) -> QPointF:
            x = left + ((point[0] - min_x) / x_span) * width
            y = top + height - ((point[1] - min_y) / y_span) * height
            return QPointF(x, y)

        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)
        for index in range(5):
            fraction = index / 4
            y = top + height * fraction
            painter.setPen(QPen(QColor("#E3E9EC"), 1))
            painter.drawLine(QPointF(left, y), QPointF(left + width, y))
            value = max_y - y_span * fraction
            painter.setPen(QColor("#566D7C"))
            painter.drawText(
                QRectF(4, y - 9, left - 10, 18),
                Qt.AlignmentFlag.AlignRight,
                f"{value:.2f}%",
            )

        painter.setPen(QPen(QColor("#005EB8"), 2.6))
        fitted = QPolygonF([map_point(point) for point in curve.fitted_points])
        if fitted.size() >= 2:
            painter.drawPolyline(fitted)

        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.setBrush(QColor("#40C1AC"))
        for point in curve.observed_points:
            painter.drawEllipse(map_point(point), 4.0, 4.0)

        if highlight is not None and highlight.curve_id == curve.curve_id:
            selected = map_point((highlight.tenor, highlight.market_yield))
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.setBrush(QColor("#FF8200"))
            painter.drawEllipse(selected, 6.5, 6.5)
            painter.setPen(QColor("#00345F"))
            painter.drawText(
                QRectF(selected.x() + 8, selected.y() - 26, 170, 22),
                Qt.AlignmentFlag.AlignLeft,
                f"{highlight.series} · {highlight.spread_bp:+.1f} pb",
            )

        painter.setPen(QColor("#566D7C"))
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
    """Mesa de Mercado: curva, valor relativo, universo PiPCA y rotación."""

    def __init__(self, presenter: MarketPresenter | None = None) -> None:
        super().__init__()
        self.setObjectName("marketWorkspace")
        self._presenter = presenter or MarketPresenter()
        self._view_model = self._presenter.build_view_model()
        self._filtered_market_rows: tuple[RelativeValueViewRow, ...] = ()
        self._filtered_rotation_rows: tuple[RotationViewRow, ...] = ()
        self._detail_labels: dict[str, QLabel] = {}
        self._selected_rv: RelativeValueViewRow | None = None
        self._build_ui()
        self.bind_view_model(self._view_model)

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D5DEE3; border-radius:7px; margin-top:8px; "
            "font-weight:700; color:#005EB8; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )

    @staticmethod
    def _status_style() -> str:
        return (
            "padding:5px 9px; background:#F0F8FC; border:1px solid #D5DEE3; "
            "border-radius:5px; color:#00345F; font-weight:600;"
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(7)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("MERCADO · CURVAS Y VALOR RELATIVO")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color:#00345F;")
        subtitle = QLabel(
            "PiPCA · Nelson-Siegel · screener de valor relativo · universo de mercado · rotación"
        )
        subtitle.setStyleSheet("color:#566D7C; font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_row.addLayout(title_box)
        title_row.addStretch(1)
        self._date_label = QLabel("-")
        self._date_label.setStyleSheet(self._status_style())
        title_row.addWidget(self._date_label)
        root.addLayout(title_row)

        self._summary_view = MarketSummaryView(self._view_model.summary)
        root.addWidget(self._summary_view)

        analytical = QSplitter(Qt.Orientation.Horizontal)
        analytical.setObjectName("marketAnalyticalSplitter")
        analytical.setChildrenCollapsible(False)

        curve_panel = QWidget()
        curve_layout = QVBoxLayout(curve_panel)
        curve_layout.setContentsMargins(0, 0, 0, 0)
        curve_layout.setSpacing(6)
        curve_toolbar = QHBoxLayout()
        curve_toolbar.addWidget(QLabel("Curva:"))
        self._curve_selector = QComboBox()
        self._curve_selector.setMinimumWidth(240)
        self._curve_selector.currentIndexChanged.connect(self._on_curve_changed)
        curve_toolbar.addWidget(self._curve_selector)
        curve_toolbar.addStretch(1)
        self._curve_metrics = QLabel("")
        self._curve_metrics.setStyleSheet("color:#566D7C; font-weight:600; font-size:9px;")
        curve_toolbar.addWidget(self._curve_metrics)
        curve_layout.addLayout(curve_toolbar)

        curve_group = QGroupBox("Curva de rendimiento · observado vs modelo oficial")
        curve_group.setStyleSheet(self._group_style())
        curve_group_layout = QVBoxLayout(curve_group)
        curve_group_layout.setContentsMargins(8, 9, 8, 6)
        self._curve_chart = _MarketCurveChart()
        curve_group_layout.addWidget(self._curve_chart, 1)
        legend = QLabel("● PiPCA observado     ━ Nelson-Siegel     ● Instrumento seleccionado")
        legend.setStyleSheet("color:#566D7C; padding:2px 8px; font-size:8px;")
        curve_group_layout.addWidget(legend)
        curve_layout.addWidget(curve_group, 1)
        analytical.addWidget(curve_panel)

        self._rv_tabs = QTabWidget()
        self._rv_tabs.setObjectName("marketRelativeValueTabs")
        self._rv_tabs.setDocumentMode(True)
        self._rv_tabs.setStyleSheet(
            "QTabBar::tab {padding:7px 14px; font-weight:600;}"
            "QTabBar::tab:selected {color:#005EB8; border-bottom:2px solid #00A9E0;}"
        )

        self._relative_value_view = RelativeValueView(self._view_model.portfolio_relative_value)
        self._relative_value_view.table().currentCellChanged.connect(
            self._on_portfolio_selection_changed
        )
        self._rv_tabs.addTab(self._relative_value_view, "RV Portafolio")

        market_tab = QWidget()
        market_layout = QVBoxLayout(market_tab)
        market_layout.setContentsMargins(0, 5, 0, 0)
        market_layout.setSpacing(5)
        market_filters = QHBoxLayout()
        market_filters.addWidget(QLabel("Curva"))
        self._market_curve_filter = self._curve_filter_combo()
        market_filters.addWidget(self._market_curve_filter)
        market_filters.addWidget(QLabel("Clasificación"))
        self._market_class_filter = QComboBox()
        self._market_class_filter.addItems(("TODAS", "BARATO", "NEUTRAL", "CARO"))
        market_filters.addWidget(self._market_class_filter)
        market_filters.addWidget(QLabel("Portafolio"))
        self._market_portfolio_filter = QComboBox()
        self._market_portfolio_filter.addItems(("TODOS", "EN PORTAFOLIO", "FUERA PORTAFOLIO"))
        market_filters.addWidget(self._market_portfolio_filter)
        market_filters.addStretch(1)
        market_layout.addLayout(market_filters)
        self._market_table = self._new_table(
            (
                "Serie",
                "Moneda",
                "Clasificación",
                "Diferencial",
                "TIR Mdo.",
                "TIR NS",
                "Plazo",
                "Precio",
                "Portafolio",
            )
        )
        self._market_table.currentCellChanged.connect(self._on_market_selection_changed)
        market_layout.addWidget(self._market_table, 1)
        self._rv_tabs.addTab(market_tab, "RV Mercado")

        rotation_tab = QWidget()
        rotation_layout = QVBoxLayout(rotation_tab)
        rotation_layout.setContentsMargins(0, 5, 0, 0)
        rotation_layout.setSpacing(5)
        rotation_filters = QHBoxLayout()
        rotation_filters.addWidget(QLabel("Curva"))
        self._rotation_curve_filter = self._curve_filter_combo()
        rotation_filters.addWidget(self._rotation_curve_filter)
        rotation_filters.addWidget(QLabel("Estado"))
        self._rotation_status_filter = QComboBox()
        self._rotation_status_filter.addItems(("TODOS", "CANDIDATO", "REVISAR", "DESCARTAR"))
        rotation_filters.addWidget(self._rotation_status_filter)
        rotation_filters.addWidget(QLabel("Destino"))
        self._rotation_portfolio_filter = QComboBox()
        self._rotation_portfolio_filter.addItems(("TODOS", "FUERA PORTAFOLIO", "EN PORTAFOLIO"))
        rotation_filters.addWidget(self._rotation_portfolio_filter)
        rotation_filters.addStretch(1)
        rotation_layout.addLayout(rotation_filters)
        self._rotation_table = self._new_table(
            (
                "Origen",
                "Destino",
                "Moneda",
                "Δ Diferencial",
                "Δ TIR",
                "Δ Plazo",
                "Score",
                "Estado",
                "Señal",
                "Destino Port.",
            )
        )
        self._rotation_table.currentCellChanged.connect(self._on_rotation_selection_changed)
        rotation_layout.addWidget(self._rotation_table, 1)
        self._rotation_explanation = QPlainTextEdit()
        self._rotation_explanation.setReadOnly(True)
        self._rotation_explanation.setMaximumHeight(72)
        self._rotation_explanation.setPlaceholderText(
            "Seleccione una alternativa para ver la explicación del screening."
        )
        rotation_layout.addWidget(self._rotation_explanation)
        self._rv_tabs.addTab(rotation_tab, "Rotación")

        analytical.addWidget(self._rv_tabs)
        analytical.setStretchFactor(0, 3)
        analytical.setStretchFactor(1, 2)
        analytical.setSizes([820, 610])
        root.addWidget(analytical, 1)

        detail_group = QGroupBox("Detalle del instrumento seleccionado")
        detail_group.setStyleSheet(self._group_style())
        detail_group.setMaximumHeight(128)
        detail = QGridLayout(detail_group)
        detail.setContentsMargins(10, 10, 10, 7)
        detail.setHorizontalSpacing(10)
        detail.setVerticalSpacing(4)
        fields = (
            ("series", "Serie"),
            ("issuer", "Emisor"),
            ("currency", "Moneda"),
            ("classification", "Clasificación"),
            ("market_yield", "TIR Mercado"),
            ("curve_yield", "TIR Curva"),
            ("spread_bp", "Diferencial"),
            ("tenor", "Plazo"),
            ("market_value_crc", "Valor Mercado"),
            ("market_price", "Precio"),
            ("position_count", "Posiciones"),
            ("in_portfolio", "En portafolio"),
        )
        for index, (key, caption) in enumerate(fields):
            row = index // 4
            pair = index % 4
            caption_label = QLabel(caption)
            caption_label.setStyleSheet("color:#7B8D98; font-size:8px;")
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_label.setStyleSheet("color:#00345F; font-weight:700;")
            self._detail_labels[key] = value_label
            detail.addWidget(caption_label, row, pair * 2)
            detail.addWidget(value_label, row, pair * 2 + 1)
        root.addWidget(detail_group)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#566D7C; padding:2px 3px; font-size:8px;")
        root.addWidget(self._status)

        for combo in (
            self._market_curve_filter,
            self._market_class_filter,
            self._market_portfolio_filter,
        ):
            combo.currentIndexChanged.connect(self._bind_market_rows)
        for combo in (
            self._rotation_curve_filter,
            self._rotation_status_filter,
            self._rotation_portfolio_filter,
        ):
            combo.currentIndexChanged.connect(self._bind_rotation_rows)

    @staticmethod
    def _curve_filter_combo() -> QComboBox:
        combo = QComboBox()
        combo.addItem("Todas", "")
        combo.addItem("Gobierno CRC", "GOBIERNO_CRC")
        combo.addItem("Gobierno USD", "GOBIERNO_USD")
        combo.addItem("BCCR CRC", "BCCR_CRC")
        return combo

    @staticmethod
    def _new_table(headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(list(headers))
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(27)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        table.setStyleSheet(
            "QHeaderView::section {background:#005EB8; color:#FFFFFF; border:none; "
            "border-right:1px solid #1675C5; padding:6px 5px; font-weight:700;}"
            "QTableWidget {selection-background-color:#DDEFFA; selection-color:#00345F;}"
        )
        return table

    @staticmethod
    def _set_item(
        table: QTableWidget,
        row: int,
        column: int,
        text: str,
        source_index: int,
        *,
        numeric: bool = False,
    ) -> None:
        item = QTableWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, source_index)
        if numeric:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table.setItem(row, column, item)

    @staticmethod
    def _classification_style(item: QTableWidgetItem, value: str) -> None:
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        token = value.strip().upper()
        if token == "BARATO":
            item.setForeground(QColor("#167A68"))
        elif token == "CARO":
            item.setForeground(QColor("#B42335"))
        else:
            item.setForeground(QColor("#566D7C"))

    @staticmethod
    def _rotation_style(item: QTableWidgetItem, value: str) -> None:
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        token = value.strip().upper()
        if token == "CANDIDATO":
            item.setForeground(QColor("#167A68"))
        elif token == "REVISAR":
            item.setForeground(QColor("#A95B00"))
        elif token == "DESCARTAR":
            item.setForeground(QColor("#B42335"))

    def _on_curve_changed(self, _index: int) -> None:
        curve_id = str(self._curve_selector.currentData() or "")
        curve = next((item for item in self._view_model.curves if item.curve_id == curve_id), None)
        self._curve_chart.set_curve(curve, self._selected_rv)
        if curve is None:
            self._curve_metrics.setText("")
            return
        self._curve_metrics.setText(
            f"{curve.official_model} · {curve.observation_count} obs. · "
            f"RMSE {curve.rmse:.4f} · R² {curve.r_squared:.4f}"
        )

    def _on_portfolio_selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if current_row < 0:
            return
        source_index = self._relative_value_view.selected_source_index()
        if source_index is None or source_index >= len(self._view_model.portfolio_relative_value):
            return
        self._show_relative_value_detail(self._view_model.portfolio_relative_value[source_index])

    def _on_market_selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if current_row < 0:
            return
        item = self._market_table.item(current_row, 0)
        if item is None:
            return
        try:
            row = self._filtered_market_rows[int(item.data(Qt.ItemDataRole.UserRole))]
        except (TypeError, ValueError, IndexError):
            return
        self._show_relative_value_detail(row)

    def _on_rotation_selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if current_row < 0:
            return
        item = self._rotation_table.item(current_row, 0)
        if item is None:
            return
        try:
            row = self._filtered_rotation_rows[int(item.data(Qt.ItemDataRole.UserRole))]
        except (TypeError, ValueError, IndexError):
            return
        self._rotation_explanation.setPlainText(row.explanation)

    def _bind_market_rows(self) -> None:
        curve_filter = str(self._market_curve_filter.currentData() or "")
        class_filter = self._market_class_filter.currentText().strip().upper()
        portfolio_filter = self._market_portfolio_filter.currentText().strip().upper()
        filtered: list[RelativeValueViewRow] = []
        for row in self._view_model.market_relative_value:
            if curve_filter and row.curve_id != curve_filter:
                continue
            if class_filter != "TODAS" and row.classification.strip().upper() != class_filter:
                continue
            if portfolio_filter == "EN PORTAFOLIO" and row.in_portfolio is not True:
                continue
            if portfolio_filter == "FUERA PORTAFOLIO" and row.in_portfolio is not False:
                continue
            filtered.append(row)
        self._filtered_market_rows = tuple(filtered)

        table = self._market_table
        table.setSortingEnabled(False)
        table.clearContents()
        table.setRowCount(len(filtered))
        for row_index, row in enumerate(filtered):
            values = (
                row.series,
                row.currency or "-",
                row.classification,
                f"{row.spread_bp:+.1f} pb",
                f"{row.market_yield:.3f}%",
                f"{row.curve_yield:.3f}%",
                f"{row.tenor:.2f}a",
                "-" if row.market_price is None else f"{row.market_price:,.4f}",
                "Sí" if row.in_portfolio is True else "No" if row.in_portfolio is False else "-",
            )
            for column, value in enumerate(values):
                self._set_item(table, row_index, column, value, row_index, numeric=column >= 3)
                if column == 2:
                    item = table.item(row_index, column)
                    if item is not None:
                        self._classification_style(item, row.classification)
        table.setSortingEnabled(True)
        if filtered:
            table.selectRow(0)
        self._rv_tabs.setTabText(1, f"RV Mercado ({len(filtered)})")

    def _bind_rotation_rows(self) -> None:
        curve_filter = str(self._rotation_curve_filter.currentData() or "")
        status_filter = self._rotation_status_filter.currentText().strip().upper()
        portfolio_filter = self._rotation_portfolio_filter.currentText().strip().upper()
        filtered: list[RotationViewRow] = []
        for row in self._view_model.rotation_rows:
            if curve_filter and row.curve_id != curve_filter:
                continue
            if status_filter != "TODOS" and row.screening_status.strip().upper() != status_filter:
                continue
            target = row.target_in_portfolio.strip().upper()
            if portfolio_filter == "EN PORTAFOLIO" and target not in {"SÍ", "SI"}:
                continue
            if portfolio_filter == "FUERA PORTAFOLIO" and target != "NO":
                continue
            filtered.append(row)
        self._filtered_rotation_rows = tuple(filtered)

        table = self._rotation_table
        table.setSortingEnabled(False)
        table.clearContents()
        table.setRowCount(len(filtered))
        for row_index, row in enumerate(filtered):
            values = (
                row.source_series,
                row.target_series,
                row.currency or "-",
                f"{row.spread_improvement_bp:+.1f} pb",
                f"{row.yield_improvement_bp:+.1f} pb",
                f"{row.tenor_difference_years:+.2f}a",
                f"{row.rotation_score:.2f}",
                row.screening_status,
                row.signal_type or "-",
                row.target_in_portfolio or "-",
            )
            for column, value in enumerate(values):
                self._set_item(
                    table, row_index, column, value, row_index, numeric=column in {3, 4, 5, 6}
                )
                if column == 7:
                    item = table.item(row_index, column)
                    if item is not None:
                        self._rotation_style(item, row.screening_status)
        table.setSortingEnabled(True)
        if filtered:
            table.selectRow(0)
        else:
            self._rotation_explanation.clear()
        self._rv_tabs.setTabText(2, f"Rotación ({len(filtered)})")

    @staticmethod
    def _display_bool(value: bool | None) -> str:
        if value is True:
            return "Sí"
        if value is False:
            return "No"
        return "-"

    def _show_relative_value_detail(self, row: RelativeValueViewRow) -> None:
        self._selected_rv = row
        values = {
            "series": row.series,
            "issuer": row.issuer,
            "currency": row.currency or "-",
            "classification": row.classification,
            "market_yield": f"{row.market_yield:.4f}%",
            "curve_yield": f"{row.curve_yield:.4f}%",
            "spread_bp": f"{row.spread_bp:+.2f} pb",
            "tenor": f"{row.tenor:.2f} años",
            "market_value_crc": (
                "-"
                if row.market_value_crc is None
                else f"₡{row.market_value_crc / 1_000_000:,.2f} MM"
            ),
            "market_price": "-" if row.market_price is None else f"{row.market_price:,.4f}",
            "position_count": str(row.position_count) if row.position_count else "-",
            "in_portfolio": self._display_bool(row.in_portfolio),
        }
        for key, value in values.items():
            self._detail_labels[key].setText(value)

        index = self._curve_selector.findData(row.curve_id)
        if index >= 0 and index != self._curve_selector.currentIndex():
            self._curve_selector.setCurrentIndex(index)
        else:
            self._curve_chart.set_highlight(row)

    def refresh(self) -> None:
        self.bind_view_model(self._presenter.refresh())

    def bind_view_model(self, view_model: MarketViewModel) -> None:
        self._view_model = view_model
        self._summary_view.bind_summary(view_model.summary)
        self._date_label.setText(f"Corte: {getattr(view_model.summary, 'market_date', '-')}")
        self._relative_value_view.bind_rows(view_model.portfolio_relative_value)
        self._rv_tabs.setTabText(0, f"RV Portafolio ({len(view_model.portfolio_relative_value)})")

        current_curve = str(self._curve_selector.currentData() or "")
        self._curve_selector.blockSignals(True)
        self._curve_selector.clear()
        for curve in view_model.curves:
            self._curve_selector.addItem(curve.label, curve.curve_id)
        target_curve = view_model.selected_curve or current_curve
        target_index = self._curve_selector.findData(target_curve) if target_curve else -1
        if target_index < 0 and self._curve_selector.count():
            target_index = 0
        if target_index >= 0:
            self._curve_selector.setCurrentIndex(target_index)
        self._curve_selector.blockSignals(False)

        self._bind_market_rows()
        self._bind_rotation_rows()
        if view_model.portfolio_relative_value:
            self._show_relative_value_detail(view_model.portfolio_relative_value[0])
        elif view_model.market_relative_value:
            self._show_relative_value_detail(view_model.market_relative_value[0])
        else:
            self._selected_rv = None
            self._on_curve_changed(target_index)
        self._on_curve_changed(self._curve_selector.currentIndex())

        message = (
            getattr(view_model.summary, "configuration_message", "")
            or view_model.error
            or view_model.status
        )
        self._status.setText(str(message))

    def view_model(self) -> MarketViewModel:
        return self._view_model
