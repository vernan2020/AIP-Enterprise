from __future__ import annotations

from aip.ui.modules.portfolio.models.portfolio_row import PortfolioRow
from aip.ui.modules.portfolio.models.portfolio_summary import PortfolioSummary
from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel
from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView
from aip.ui.navigation.menu_registry import MenuRegistry
from aip.ui.navigation.navigation_manager import NavigationManager
from aip.ui.navigation.routes import Route
from aip.ui.modules.portfolio.routing.portfolio_route import PortfolioRoute
from aip.ui.shell.main_window import MainWindow
from aip.ui.shell.workspace import Workspace


def test_portfolio_route_and_menu_registry_integration() -> None:
    navigation = NavigationManager()
    menu_registry = MenuRegistry()
    navigation.register(PortfolioRoute())
    menu_registry.register("portfolio", "Portfolio")

    navigation.navigate("portfolio")

    assert navigation.current_route().id == "portfolio"
    assert menu_registry.route_label("portfolio") == "Portfolio"


def test_workspace_duplicate_tabs_are_prevented_and_reopened(qt_app) -> None:
    workspace = Workspace()
    view = PortfolioView()

    workspace.open_tab("Portfolio", view)
    workspace.open_tab("Portfolio", view)
    assert workspace.count() == 1

    workspace.close_tab("Portfolio")
    assert workspace.count() == 0

    workspace.open_tab("Portfolio", view)
    assert workspace.count() == 1


def test_workspace_pin_and_unpin_toggle(qt_app) -> None:
    workspace = Workspace()
    workspace.open_tab("Portfolio", PortfolioView())

    workspace.pin_tab("Portfolio")
    assert workspace.is_pinned("Portfolio") is True

    workspace.unpin_tab("Portfolio")
    assert workspace.is_pinned("Portfolio") is False


def test_main_window_opens_portfolio_workspace_from_shell(qt_app) -> None:
    window = MainWindow()
    window.open_workspace("portfolio")

    tab_titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]
    assert "Portfolio" in tab_titles


def test_portfolio_view_updates_from_view_model(qt_app) -> None:
    view = PortfolioView()
    summary = PortfolioSummary(
        portfolio_name="Portfolio",
        valuation_date="2026-07-29",
        market_value="100",
        book_value="90",
        total_positions=1,
        weighted_yield="2%",
        modified_duration="1.0",
        hqla_percent="50%",
        mil_eligible_percent="60%",
    )
    row = PortfolioRow(
        isin="US1",
        issuer="Issuer",
        instrument="Bond",
        currency="USD",
        nominal="10",
        market_value="10",
        book_value="9",
        yield_value="2%",
        modified_duration="1.0",
        classification="Govt",
        hqla_status="Eligible",
        mil_status="Eligible",
        recommendation="Hold",
    )
    view_model = PortfolioViewModel(
        summary=summary,
        rows=(row,),
        selected_isin="US1",
        theme="dark",
        status="loaded",
        warnings=("warning",),
        calculation_id="calc-1",
        correlation_id="corr-1",
    )

    view.bind_view_model(view_model)

    assert view.view_model() is view_model
    assert view.view_model().summary.portfolio_name == "Portfolio"
    assert view.view_model().warnings[0] == "warning"
