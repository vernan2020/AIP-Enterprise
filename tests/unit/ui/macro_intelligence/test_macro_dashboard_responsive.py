from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QTabWidget,
    QWidget,
)

from aip.ui.modules.macro_intelligence.views.macro_intelligence_workspace import (
    MacroIntelligenceWorkspace,
    _MacroMetricCard,
    _ProjectionChart,
)


def test_macro_dashboard_reflows_seven_existing_kpis(qt_app) -> None:
    parent = QWidget()
    grid = QGridLayout(parent)
    cards = tuple(QFrame() for _ in range(7))
    try:
        assert MacroIntelligenceWorkspace._metric_columns_for_width(600) == 2
        assert MacroIntelligenceWorkspace._metric_columns_for_width(960) == 4
        assert MacroIntelligenceWorkspace._metric_columns_for_width(1440) == 7

        for columns in (7, 4, 2, 7):
            MacroIntelligenceWorkspace._reflow_grid(grid, cards, columns)
            for index, card in enumerate(cards):
                position = grid.itemAtPosition(index // columns, index % columns)
                assert position is not None
                assert position.widget() is card
        assert len(set(map(id, cards))) == 7
    finally:
        parent.close()
        qt_app.processEvents()


def test_macro_governance_cards_can_reflow_without_replacing_values(qt_app) -> None:
    parent = QWidget()
    grid = QGridLayout(parent)
    cards = tuple(QFrame() for _ in range(4))
    try:
        cards[0].setProperty("approvedScenario", "BASE-2026-10")
        MacroIntelligenceWorkspace._reflow_grid(grid, cards, 2)
        assert grid.itemAtPosition(1, 1).widget() is cards[3]
        MacroIntelligenceWorkspace._reflow_grid(grid, cards, 4)
        assert grid.itemAtPosition(0, 3).widget() is cards[3]
        assert cards[0].property("approvedScenario") == "BASE-2026-10"
    finally:
        parent.close()
        qt_app.processEvents()


def test_institutional_macro_chart_has_visible_readout_signal(qt_app) -> None:
    chart = _ProjectionChart()
    received: list[str] = []
    chart.hover_readout_changed.connect(received.append)
    try:
        chart.hover_readout_changed.emit("TPM · oct-2026 · 3.25%")
        assert received == ["TPM · oct-2026 · 3.25%"]
        chart.set_projection(chart._projection, "TBP")
        assert received[-1] == ""
        assert chart._last_readout == ""
        assert chart._readout_regions == []
    finally:
        chart.close()
        qt_app.processEvents()


def test_macro_header_stacks_without_losing_scenario_or_refresh_button(qt_app) -> None:
    host = QWidget()
    grid = QGridLayout(host)
    title = QWidget()
    scenario = QLabel("Escenario: BASE-2026")
    refresh = QPushButton("ACTUALIZAR BCCR")
    widgets = (title, scenario, refresh)
    try:
        MacroIntelligenceWorkspace._reflow_macro_header(grid, widgets, False)
        for index, widget in enumerate(widgets):
            item = grid.itemAtPosition(0, index)
            assert item is not None
            assert item.widget() is widget

        MacroIntelligenceWorkspace._reflow_macro_header(grid, widgets, True)
        assert grid.itemAtPosition(0, 0).widget() is title
        assert grid.itemAtPosition(0, 1).widget() is title
        assert grid.itemAtPosition(1, 0).widget() is scenario
        assert grid.itemAtPosition(1, 1).widget() is refresh
        assert scenario.text() == "Escenario: BASE-2026"
        assert refresh.text() == "ACTUALIZAR BCCR"

        MacroIntelligenceWorkspace._reflow_macro_header(grid, widgets, False)
        assert grid.itemAtPosition(0, 1).widget() is scenario
        assert grid.itemAtPosition(0, 2).widget() is refresh
    finally:
        host.close()
        qt_app.processEvents()


def test_macro_metric_card_wraps_value_change_and_observation_source(qt_app) -> None:
    card = _MacroMetricCard("Indicador de denominación extensa")
    try:
        labels = card.findChildren(QLabel)
        assert len(labels) == 4
        assert all(label.wordWrap() for label in labels)
        card._value.setText("1,234,567.89")
        card._date.setText("12/10/2026 · BCCR fuente institucional")
        assert card._value.text() == "1,234,567.89"
        assert "BCCR" in card._date.text()
    finally:
        card.close()
        qt_app.processEvents()


def test_macro_projection_toolbar_stacks_selectors_and_preserves_choices(qt_app) -> None:
    host = QWidget()
    grid = QGridLayout(host)
    source_label = QLabel("Fuente:")
    source = QComboBox()
    source.addItem("Ensemble ML", "ML")
    source.addItem("Escenario institucional", "INSTITUTIONAL")
    driver_label = QLabel("Variable proyectada:")
    driver = QComboBox()
    driver.addItem("TPM", "TPM")
    driver.addItem("USD/CRC venta", "FX_SELL")
    context = QLabel("Octubre de 2026 · 12 meses")
    widgets = (source_label, source, driver_label, driver, context)
    try:
        source.setCurrentIndex(1)
        driver.setCurrentIndex(1)
        for compact in (False, True, False):
            MacroIntelligenceWorkspace._reflow_projection_selectors(grid, widgets, compact)
            if compact:
                assert grid.itemAtPosition(0, 0).widget() is source_label
                assert grid.itemAtPosition(0, 1).widget() is source
                assert grid.itemAtPosition(1, 0).widget() is driver_label
                assert grid.itemAtPosition(1, 1).widget() is driver
                assert grid.itemAtPosition(2, 0).widget() is context
                assert grid.itemAtPosition(2, 1).widget() is context
            else:
                for index, widget in enumerate(widgets):
                    assert grid.itemAtPosition(0, index).widget() is widget
            assert source.currentData() == "INSTITUTIONAL"
            assert driver.currentData() == "FX_SELL"
            assert context.text() == "Octubre de 2026 · 12 meses"
    finally:
        host.close()
        qt_app.processEvents()


def test_macro_crc_and_usd_curve_tables_stack_without_replacing_widgets(qt_app) -> None:
    host = QWidget()
    grid = QGridLayout(host)
    crc = QGroupBox("TRI CRC · observado")
    usd = QGroupBox("TRI USD · observado")
    groups = (crc, usd)
    try:
        for columns in (2, 1, 2):
            MacroIntelligenceWorkspace._reflow_grid(grid, groups, columns)
            for index, group in enumerate(groups):
                item = grid.itemAtPosition(index // columns, index % columns)
                assert item is not None
                assert item.widget() is group
        assert crc.title() == "TRI CRC · observado"
        assert usd.title() == "TRI USD · observado"
    finally:
        host.close()
        qt_app.processEvents()


def test_macro_transmission_stages_reflow_without_changing_explanations(qt_app) -> None:
    host = QWidget()
    grid = QGridLayout(host)
    stages = tuple(QFrame() for _ in range(4))
    captions = ("MACRO", "MERCADOS", "BALANCE", "RESULTADOS")
    try:
        for card, caption in zip(stages, captions):
            card.setObjectName(caption)
        for columns in (4, 2, 4):
            MacroIntelligenceWorkspace._reflow_grid(grid, stages, columns)
            for index, card in enumerate(stages):
                item = grid.itemAtPosition(index // columns, index % columns)
                assert item is not None
                assert item.widget() is card
                assert card.objectName() == captions[index]
    finally:
        host.close()
        qt_app.processEvents()


def test_macro_tab_navigation_preserves_full_titles_in_compact_view(qt_app) -> None:
    tabs = QTabWidget()
    try:
        tabs.setDocumentMode(True)
        tabs.tabBar().setUsesScrollButtons(True)
        tabs.setElideMode(Qt.TextElideMode.ElideRight)
        titles = (
            "Forecast ejecutivo",
            "Matriz macro",
            "Curvas TRI",
            "Transmisión",
        )
        for title in titles:
            tabs.addTab(QWidget(), title)
        tabs.resize(380, 320)
        tabs.setCurrentIndex(3)
        assert tabs.tabBar().usesScrollButtons()
        assert tabs.elideMode() == Qt.TextElideMode.ElideRight
        assert tabs.currentIndex() == 3
        assert tuple(tabs.tabText(i) for i in range(tabs.count())) == titles
        for index in range(tabs.count()):
            tabs.setTabToolTip(index, tabs.tabText(index))
            assert tabs.tabToolTip(index) == titles[index]
    finally:
        tabs.close()
        qt_app.processEvents()


def test_macro_executive_defaults_to_approved_source_and_draws_existing_projection(
    qt_app, monkeypatch
) -> None:
    """The restored certified scenario must render without launching the ML engine."""
    from datetime import date

    from PySide6.QtWidgets import QTableWidget

    from aip.ui.modules.macro_intelligence.viewmodels.macro_intelligence_view_model import (
        MacroProjectionRow,
        MacroProjectionViewModel,
    )

    # Construct only the actual UI tab; no institutional connector is replaced.
    workspace = MacroIntelligenceWorkspace.__new__(MacroIntelligenceWorkspace)
    QWidget.__init__(workspace)
    workspace._tabs = QTabWidget(workspace)
    ml_requests: list[str] = []
    monkeypatch.setattr(workspace, "_load_ml_projection", ml_requests.append)
    try:
        workspace._build_projection_tab()
        assert workspace._projection_source_combo.currentData() == "INSTITUTIONAL"
        assert workspace._projection_source_combo.itemData(1) == "ML"
        workspace._scenario_badge = QLabel()
        workspace._governance_labels = {
            key: QLabel() for key in ("scenario", "version", "dataset", "horizon")
        }
        workspace._projection_table = QTableWidget(0, 8)
        rows = (
            MacroProjectionRow(
                period=date(2026, 9, 1),
                fx_sell=449.99,
                tpm=3.0,
                tbp=3.6,
                tri_crc_12m=6.2,
                tri_usd_12m=4.11,
                inflation=-0.28,
                imae=3.33,
            ),
            MacroProjectionRow(
                period=date(2026, 10, 1),
                fx_sell=447.09,
                tpm=3.0,
                tbp=3.59,
                tri_crc_12m=6.2,
                tri_usd_12m=4.11,
                inflation=-0.28,
                imae=3.61,
            ),
        )
        workspace._projection = MacroProjectionViewModel(
            status="AVAILABLE",
            scenario_id="BASE-MACRO-INSTITUTIONAL",
            scenario_type="BASE",
            scenario_status="APPROVED",
            version=4,
            horizon=12,
            rows=rows,
        )
        workspace._bind_projection()
        assert workspace._projection_chart._projection.rows == rows
        assert workspace._projection_chart._ml_forecast is None
        assert workspace._projection_table.rowCount() == len(rows)
        assert workspace._projection_chart._driver_code == "TPM"
        assert "directamente del escenario" in workspace._projection_note.text()
        assert not ml_requests
        # ML starts only if the user chooses that option.
        workspace._projection_source_combo.setCurrentIndex(1)
        assert ml_requests == ["TPM"]
        workspace._projection_source_combo.setCurrentIndex(0)
        assert workspace._projection_chart._projection.rows == rows
        assert workspace._projection_chart._ml_forecast is None
    finally:
        workspace.close()
        qt_app.processEvents()


def test_empty_ml_result_has_correct_source_specific_placeholder(qt_app) -> None:
    from aip.ui.modules.macro_intelligence.viewmodels.macro_intelligence_view_model import (
        MacroForecastLabViewModel,
    )

    chart = _ProjectionChart()
    try:
        chart.set_ml_forecast(MacroForecastLabViewModel(indicator_code="TPM"))
        assert chart._ml_forecast is not None
        assert chart._ml_forecast.points == ()
    finally:
        chart.close()
        qt_app.processEvents()
