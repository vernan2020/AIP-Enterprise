from __future__ import annotations

from aip.ui.modules.liquidity.presenters.liquidity_presenter import LiquidityPresenter
from aip.ui.modules.liquidity.viewmodels.liquidity_view_model import LiquidityViewModel


def test_presenter_builds_view_model_and_supports_filters() -> None:
    presenter = LiquidityPresenter()
    view_model = presenter.build_view_model(theme="dark")

    assert isinstance(view_model, LiquidityViewModel)
    assert view_model.theme == "dark"
    assert view_model.summary.cash_position == "100.00"
    assert view_model.cashflow_rows[0].bucket == "T+0"
    assert view_model.status == "loaded"

    filtered = presenter.apply_filters({"currency": "USD"})
    selected = presenter.select("cash")

    assert filtered.filters["currency"] == "USD"
    assert selected.selected_section == "cash"
