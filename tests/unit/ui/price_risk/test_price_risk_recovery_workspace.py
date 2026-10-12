from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QTabWidget

from aip.ui.modules.price_risk.models.price_risk_row import RateShockViewRow, RiskChartPoint
from aip.ui.modules.price_risk.viewmodels.price_risk_view_model import PriceRiskViewModel
from aip.ui.modules.price_risk.views.price_risk_view import PriceRiskView


class _StubPresenter:
    def build_view_model(self, *, force_refresh: bool = False) -> PriceRiskViewModel:
        return _view_model()


def _view_model() -> PriceRiskViewModel:
    return PriceRiskViewModel(
        valuation_date="27/08/2026",
        var_crc="₡125.00 MM",
        var_percent="0.1500%",
        eligible_market_value="₡210,000.00 MM",
        calculated_market_value="₡200,000.00 MM",
        policy_excluded_market_value="₡80,000.00 MM",
        history_excluded_market_value="₡10,000.00 MM",
        coverage_percent="95.24%",
        contribution_reconciliation_percent="100.0000%",
        eligible_positions=40,
        policy_excluded_positions=5,
        calculated_titles=35,
        history_excluded_titles=2,
        required_prices=521,
        horizon_observations=21,
        scenario_count=500,
        var_rank=25,
        scenario_number=31,
        scenario_start_date="01/07/2026",
        scenario_end_date="30/07/2026",
        dv01_total="₡42.00 MM",
        dv01_crc="₡35.00 MM",
        dv01_usd="₡7.00 MM",
        dv01_coverage_percent="97.00%",
        dv01_bucket_lt1_value="₡4.00 MM",
        dv01_bucket_lt1_percent="9.52%",
        dv01_bucket_lt1_market_value="₡40,000.00 MM",
        dv01_bucket_lt1_positions=8,
        dv01_bucket_1to5_value="₡21.00 MM",
        dv01_bucket_1to5_percent="50.00%",
        dv01_bucket_1to5_market_value="₡90,000.00 MM",
        dv01_bucket_1to5_positions=14,
        dv01_bucket_gt5_value="₡17.00 MM",
        dv01_bucket_gt5_percent="40.48%",
        dv01_bucket_gt5_market_value="₡70,000.00 MM",
        dv01_bucket_gt5_positions=13,
        rate_shock_coverage_percent="97.00%",
        rate_shock_status="CALCULATED",
        worst_shock="+200 pb",
        worst_delta_eve="-₡84.00 MM",
        rate_shock_rows=(
            RateShockViewRow(-200, "-200 pb", "₡84.00 MM", "₡200,084.00 MM", Decimal("84000000")),
            RateShockViewRow(200, "+200 pb", "-₡84.00 MM", "₡199,916.00 MM", Decimal("-84000000")),
        ),
        var_contribution_points=(
            RiskChartPoint("CRG0001", Decimal("16.5")),
            RiskChartPoint("CRG0002", Decimal("12.4")),
        ),
        var_pareto_points=(
            RiskChartPoint("CRG0001", Decimal("16.5"), Decimal("16.5")),
            RiskChartPoint("CRG0002", Decimal("12.4"), Decimal("28.9")),
            RiskChartPoint("CRG0003", Decimal("71.1"), Decimal("100.0")),
        ),
        issuer_contribution_points=(
            RiskChartPoint("G", Decimal("70")),
            RiskChartPoint("BCCR", Decimal("30")),
        ),
        currency_market_value_points=(
            RiskChartPoint("CRC", Decimal("180000000000"), Decimal("90")),
            RiskChartPoint("USD", Decimal("20000000000"), Decimal("10")),
        ),
        dv01_bucket_points=(
            RiskChartPoint("< 1 año", Decimal("4000000"), Decimal("9.52")),
            RiskChartPoint("1 a 5 años", Decimal("21000000"), Decimal("50.00")),
            RiskChartPoint("> 5 años", Decimal("17000000"), Decimal("40.48")),
        ),
        dv01_currency_points=(
            RiskChartPoint("CRC", Decimal("35000000"), Decimal("83.33")),
            RiskChartPoint("USD", Decimal("7000000"), Decimal("16.67")),
        ),
        rate_shock_points=(
            RiskChartPoint("-200 pb", Decimal("84000000")),
            RiskChartPoint("+200 pb", Decimal("-84000000")),
        ),
        status="CALCULATED",
    )


def test_price_risk_workspace_restores_price_simulator_and_rate_tabs(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())  # type: ignore[arg-type]
    try:
        view._bind_view_model(_view_model())
        tabs = view.findChild(QTabWidget)
        assert tabs is not None
        assert tabs.count() == 3
        assert tabs.tabText(0) == "Resumen VeR"
        assert tabs.tabText(1) == "Simulador · VeR"
        assert tabs.tabText(2) == "Riesgo de Tasa · DV01"
        assert view.view_model.status == "CALCULATED"
        assert view.view_model.required_prices == 521
        assert view.view_model.contribution_reconciliation_percent == "100.0000%"
    finally:
        view.close()
        qt_app.processEvents()


def test_price_risk_workspace_shows_rate_sensitivity_without_fabricating_nii(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())  # type: ignore[arg-type]
    try:
        view._bind_view_model(_view_model())
        assert view.view_model.dv01_total == "₡42.00 MM"
        assert view.view_model.worst_shock == "+200 pb"
        assert view.view_model.worst_delta_eve == "-₡84.00 MM"
        assert len(view.view_model.rate_shock_rows) == 2
        assert not hasattr(view.view_model, "delta_nii")
    finally:
        view.close()
        qt_app.processEvents()


def test_price_risk_kpis_reflow_without_losing_cards(qt_app) -> None:
    """Six certified KPI values remain present at compact and desktop widths."""
    view = PriceRiskView(_StubPresenter())  # type: ignore[arg-type]
    try:
        grid = view._kpi_grid
        assert grid is not None
        cards = view._kpi_cards
        assert len(cards) == 6

        for width, expected_columns in ((1280, 6), (900, 3), (620, 2), (1280, 6)):
            view._arrange_kpi_cards(width)
            assert view._kpi_columns == expected_columns
            assert grid.itemAtPosition(0, 0).widget() is cards[0]
            for index, card in enumerate(cards):
                item = grid.itemAtPosition(index // expected_columns, index % expected_columns)
                assert item is not None
                assert item.widget() is card
    finally:
        view.close()
        qt_app.processEvents()


def test_price_and_rate_chart_readout_do_not_require_windows_tooltip(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())  # type: ignore[arg-type]
    try:
        assert view._price_hover_readout.objectName() == "priceRiskHoverReadout"
        assert view._rate_hover_readout.objectName() == "rateRiskHoverReadout"
        view._contribution_chart.hover_readout_changed.emit("Serie CRG001 · +16.50%")
        assert "CRG001" in view._price_hover_readout.text()
        view._pareto_chart.hover_readout_changed.emit("Acumulado: 28.9%")
        assert "28.9%" in view._price_hover_readout.text()
        view._contribution_chart.hover_readout_changed.emit("")
        assert "Pase el cursor" in view._price_hover_readout.text()

        view._bucket_chart.hover_readout_changed.emit("< 1 año · ₡4.00 MM")
        assert "₡4.00 MM" in view._rate_hover_readout.text()
        view._shock_chart.hover_readout_changed.emit("-200 pb · ₡84.00 MM")
        assert "-200 pb" in view._rate_hover_readout.text()
        view._shock_chart.hover_readout_changed.emit("")
        assert "Pase el cursor" in view._rate_hover_readout.text()
    finally:
        view.close()
        qt_app.processEvents()


def test_rate_risk_kpi_cards_reflow_without_losing_values(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())  # type: ignore[arg-type]
    try:
        grid = view._rate_kpi_grid
        assert grid is not None
        cards = view._rate_kpi_cards
        assert len(cards) == 6
        view._kpi_labels["dv01_total"].setText("₡42.00 MM")

        for width, columns in ((1400, 6), (900, 3), (630, 2), (1400, 6)):
            view._arrange_rate_kpis(width)
            assert view._rate_kpi_columns == columns
            for index, card in enumerate(cards):
                item = grid.itemAtPosition(index // columns, index % columns)
                assert item is not None
                assert item.widget() is card
            assert view._kpi_labels["dv01_total"].text() == "₡42.00 MM"
    finally:
        view.close()
        qt_app.processEvents()


def test_var_quality_strip_reflows_all_eight_metrics_without_changing_values(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())  # type: ignore[arg-type]
    try:
        grid = view._quality_grid
        cards = view._quality_cards
        note = view._quality_note
        assert grid is not None
        assert note is not None
        assert len(cards) == 8
        assert len(view._quality_labels) == 8

        view._quality_labels["reconciliation"].setText("100.0000%")
        for width, columns in ((1440, 8), (980, 4), (680, 2), (1440, 8)):
            view._arrange_quality_cards(width)
            assert view._quality_columns == columns
            for index, card in enumerate(cards):
                item = grid.itemAtPosition(index // columns, index % columns)
                assert item is not None
                assert item.widget() is card
            note_row = len(cards) // columns
            note_item = grid.itemAtPosition(note_row, 0)
            assert note_item is not None
            assert note_item.widget() is note
            assert view._quality_labels["reconciliation"].text() == "100.0000%"
    finally:
        view.close()
        qt_app.processEvents()


def test_price_risk_chart_groups_stack_at_compact_width(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())  # type: ignore[arg-type]
    try:
        view._bind_view_model(_view_model())
        price_grid = view._var_chart_grid
        rate_grid = view._rate_chart_grid
        assert price_grid is not None
        assert rate_grid is not None
        price_groups = view._var_chart_groups
        rate_groups = view._rate_chart_groups
        assert len(price_groups) == 4
        assert len(rate_groups) == 4
        expected_var = view.view_model.var_crc
        expected_dv01 = view.view_model.dv01_total

        for width, columns in ((1300, 2), (820, 1), (1300, 2)):
            view._arrange_visual_grids(width)
            assert view._chart_columns == columns
            for grid, groups in ((price_grid, price_groups), (rate_grid, rate_groups)):
                for index, group in enumerate(groups):
                    item = grid.itemAtPosition(index // columns, index % columns)
                    assert item is not None
                    assert item.widget() is group
            assert view.view_model.var_crc == expected_var
            assert view.view_model.dv01_total == expected_dv01
        assert view._price_hover_readout.objectName() == "priceRiskHoverReadout"
        assert view._rate_hover_readout.objectName() == "rateRiskHoverReadout"
    finally:
        view.close()
        qt_app.processEvents()


def test_rate_context_reflows_without_losing_eve_or_status(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())  # type: ignore[arg-type]
    try:
        view._bind_view_model(_view_model())
        grid = view._rate_context_grid
        blocks = view._rate_context_blocks
        assert grid is not None
        assert len(blocks) == 3
        for width, columns in ((1280, 3), (650, 1), (1280, 3)):
            view._arrange_rate_context(width)
            assert view._rate_context_columns == columns
            for index, block in enumerate(blocks):
                item = grid.itemAtPosition(index // columns, index % columns)
                assert item is not None
                assert item.widget() is block
            assert view._rate_context_labels["worst_eve"].text() == "-₡84.00 MM"
            assert view._rate_context_labels["shock_status"].text() == "CALCULADO"
    finally:
        view.close()
        qt_app.processEvents()


def test_var_scenario_fields_reflow_and_keep_period_and_status(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())  # type: ignore[arg-type]
    try:
        view._bind_view_model(_view_model())
        grid = view._scenario_grid
        fields = view._scenario_fields
        assert grid is not None
        assert len(fields) == 3
        original_period = view._scenario_period.text()
        original_status = view._status_label.text()
        for width, columns in ((1200, 3), (650, 1), (1200, 3)):
            view._arrange_scenario_fields(width)
            assert view._scenario_columns == columns
            for index, field in enumerate(fields):
                item = grid.itemAtPosition(index // columns, index % columns)
                assert item is not None
                assert item.widget() is field
            note_row = (len(fields) + columns - 1) // columns
            note = grid.itemAtPosition(note_row, 0)
            assert note is not None
            assert note.widget() is view._diagnostic_label
            assert view._scenario_period.text() == original_period
            assert view._status_label.text() == original_status
        assert view._diagnostic_label.wordWrap()
    finally:
        view.close()
        qt_app.processEvents()
