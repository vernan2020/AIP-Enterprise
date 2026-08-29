from __future__ import annotations

from aip.ui.modules.portfolio.models.portfolio_row import PortfolioRow
from aip.ui.modules.portfolio.models.portfolio_summary import PortfolioSummary
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel


def test_viewmodel_is_immutable() -> None:
    summary = PortfolioSummary(
        portfolio_name="P",
        valuation_date="2026-07-29",
        market_value="1",
        book_value="1",
        total_positions=1,
        weighted_yield="1%",
        modified_duration="1",
        hqla_percent="50%",
        mil_eligible_percent="50%",
    )
    row = PortfolioRow(
        isin="A",
        issuer="Issuer",
        instrument="Instrument",
        currency="USD",
        nominal="1",
        market_value="1",
        book_value="1",
        yield_value="1%",
        modified_duration="1",
        classification="Govt",
        hqla_status="Eligible",
        mil_status="Eligible",
        recommendation="Hold",
    )
    view_model = PortfolioViewModel(
        summary=summary,
        rows=(row,),
        filters={"currency": "USD"},
        selected_isin="A",
        theme="light",
        status="loaded",
        warnings=("warn",),
        calculation_id="calc",
        correlation_id="corr",
    )

    assert view_model.summary.portfolio_name == "P"
    assert view_model.rows[0].instrument == "Instrument"
    assert view_model.filters["currency"] == "USD"
    assert view_model.selected_isin == "A"
    assert view_model.warnings[0] == "warn"
    assert view_model.status == "loaded"
    assert view_model.calculation_id == "calc"
    assert view_model.correlation_id == "corr"
    assert view_model.rows == (row,)
