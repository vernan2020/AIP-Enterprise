from __future__ import annotations

from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel


def test_presenter_builds_immutable_view_model() -> None:
    presenter = PortfolioPresenter()
    view_model = presenter.build_view_model(theme="dark")

    assert isinstance(view_model, PortfolioViewModel)
    assert view_model.theme == "dark"
    assert view_model.summary.portfolio_name == "AIP Core Portfolio"
    assert view_model.rows[0].isin == "US0000001"


def test_presenter_handles_filters_and_selection() -> None:
    presenter = PortfolioPresenter()
    view_model = presenter.apply_filters({"currency": "USD"})
    selected = presenter.select("US0000001")

    assert view_model.filters["currency"] == "USD"
    assert selected.selected_isin == "US0000001"


def test_presenter_handles_loading_empty_and_error_states() -> None:
    presenter = PortfolioPresenter()
    loading_view_model = presenter.set_loading()
    empty_view_model = presenter.empty_state()
    error_view_model = presenter.handle_application_failure("workflow failure")

    assert loading_view_model.loading is True
    assert empty_view_model.status == "empty"
    assert error_view_model.error == "workflow failure"
