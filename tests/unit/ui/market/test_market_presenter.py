from __future__ import annotations

from aip.ui.modules.market.presenters.market_presenter import MarketPresenter
from aip.ui.modules.market.viewmodels.market_view_model import MarketViewModel


def test_presenter_builds_immutable_view_model() -> None:
    presenter = MarketPresenter()
    view_model = presenter.build_view_model(theme="dark")

    assert isinstance(view_model, MarketViewModel)
    assert view_model.theme == "dark"
    assert view_model.status == "loaded"
    assert view_model.summary.market_date == "2026-07-29"
    assert view_model.curve_points[0].label == "USD 3M"


def test_presenter_supports_filters_and_selection() -> None:
    presenter = MarketPresenter()
    view_model = presenter.apply_filters({"currency": "USD"})
    selected = presenter.select("USD")

    assert view_model.filters["currency"] == "USD"
    assert selected.selected_curve == "USD"
