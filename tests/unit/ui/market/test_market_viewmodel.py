from __future__ import annotations

from aip.ui.modules.market.models.curve_point import CurvePoint
from aip.ui.modules.market.models.market_row import MarketRow
from aip.ui.modules.market.viewmodels.market_view_model import MarketViewModel


def test_view_model_is_immutable_and_serializable() -> None:
    row = MarketRow(
        issuer="Issuer",
        instrument="Bond",
        currency="USD",
        recommendation="Buy",
        confidence="High",
        spread="0.45",
        z_spread="0.40",
        benchmark_spread="0.05",
        market_value="100.00",
        book_value="98.00",
        clean_price="99.00",
        dirty_price="100.00",
        accrued_interest="1.00",
        duration="4.50",
        modified_duration="4.20",
        convexity="0.10",
        dv01="0.01",
        pvbp="0.02",
    )
    curve = CurvePoint(label="USD 3M", value="3.10", tenor="3M")
    view_model = MarketViewModel(
        summary=type("Summary", (), {"market_date": "2026-07-29", "curves_loaded": 3, "pricing_date": "2026-07-29", "relative_value_opportunities": 2, "average_yield": "3.10%", "average_duration": "4.50", "average_spread": "0.45", "market_status": "Ready"})(),
        rows=(row,),
        curve_points=(curve,),
        filters={"currency": "USD"},
        selected_curve="USD",
        theme="light",
        status="loaded",
        warnings=("synced",),
        calculation_id="calc-1",
        correlation_id="corr-1",
    )

    dumped = view_model.to_dict()

    assert view_model.filters["currency"] == "USD"
    assert dumped["selected_curve"] == "USD"
    assert dumped["rows"][0]["instrument"] == "Bond"
    assert view_model.warnings[0] == "synced"
