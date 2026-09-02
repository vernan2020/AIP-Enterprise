from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QTabWidget

from aip.ui.modules.price_risk.models.price_risk_row import RiskChartPoint
from aip.ui.modules.price_risk.viewmodels.price_risk_view_model import PriceRiskViewModel
from aip.ui.modules.price_risk.views.price_risk_view import PriceRiskView


class _StubPresenter:
    def build_view_model(self) -> PriceRiskViewModel:
        return _view_model()


def _view_model() -> PriceRiskViewModel:
    return PriceRiskViewModel(
        valuation_date="27/08/2026",
        var_crc="₡125.00 MM",
        var_percent="0.1500%",
        eligible_market_value="₡200,000.00 MM",
        coverage_percent="98.50%",
        calculated_titles=35,
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
        var_contribution_points=(
            RiskChartPoint("CRG0001", Decimal("16.5")),
            RiskChartPoint("CRG0002", Decimal("12.4")),
        ),
        var_pareto_points=(
            RiskChartPoint("CRG0001", Decimal("16.5"), Decimal("16.5")),
            RiskChartPoint("CRG0002", Decimal("12.4"), Decimal("28.9")),
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
        status="CALCULATED",
    )


def test_price_risk_workspace_restores_price_and_rate_tabs(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())
    try:
        view._bind_view_model(_view_model())
        tabs = view.findChild(QTabWidget)
        assert tabs is not None
        assert tabs.count() == 2
        assert tabs.tabText(0) == "Riesgo de Precio"
        assert tabs.tabText(1) == "Riesgo de Tasa"
        assert view.view_model.status == "CALCULATED"
        assert view.view_model.required_prices == 521
    finally:
        view.close()
        qt_app.processEvents()


def test_price_risk_workspace_keeps_irrbb_separate_from_dv01(qt_app) -> None:
    view = PriceRiskView(_StubPresenter())
    try:
        view._bind_view_model(_view_model())
        assert view.view_model.dv01_total == "₡42.00 MM"
        assert not hasattr(view.view_model, "rate_shock_plus_200")
    finally:
        view.close()
        qt_app.processEvents()
