from __future__ import annotations

from aip.product.configured.protocols import PortfolioDataProvider
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.ui.modules.portfolio.models.portfolio_row import PortfolioRow
from aip.ui.modules.portfolio.models.portfolio_summary import PortfolioSummary
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel


class PortfolioPresenter:
    """Presenter that adapts application-layer workflow results into a passive view model."""

    def __init__(self, demo_factory: DemoApplicationFactory | None = None) -> None:
        self._demo_factory = demo_factory or DemoApplicationFactory(DemoConfig(execution_mode="DEMO", demo_mode_enabled=True))
        self._correlation_id = "corr-demo-portfolio"
        self._trace_configuration()

    def _trace_configuration(self) -> None:
        config = getattr(self._demo_factory, "config", None)
        execution_mode = getattr(config, "execution_mode", "UNKNOWN")
        if execution_mode != "CONFIGURED":
            return
        try:
            provider = self._demo_factory.container.resolve(PortfolioDataProvider)
        except Exception:  # pragma: no cover - defensive UI tracing
            provider = None
        print(
            f"[portfolio-runtime] startup execution_mode={execution_mode} "
            f"provider_class={type(provider).__name__ if provider is not None else 'unavailable'} "
            f"provider_object_type={type(provider) if provider is not None else None}"
        )

    def build_view_model(self, *, theme: str = "light", filters: dict[str, str] | None = None, selected_isin: str | None = None, loading: bool = False, error: str | None = None) -> PortfolioViewModel:
        print("[portfolio-runtime] presenter.method=build_view_model")
        workflow_result = self._demo_factory.initial_load_workflow().execute(self._correlation_id)
        portfolio = workflow_result["portfolio"]
        print(
            f"[portfolio-runtime] presenter payload_type={type(portfolio).__name__} "
            f"positions={len(portfolio.get('positions', []))} valuation_date={portfolio.get('valuation_date')} "
            f"first_position={portfolio.get('positions', [{}])[0] if portfolio.get('positions') else None}"
        )
        rows = tuple(
            PortfolioRow(
                isin=position["isin"],
                issuer=position["issuer"],
                instrument=position["instrument"],
                currency=position["currency"],
                nominal=f"{position['nominal']:.0f}",
                market_value=f"{position['market_value']:.2f}",
                book_value=f"{position['book_value']:.2f}",
                yield_value=f"{position['yield_value']:.2f}%",
                modified_duration=f"{position['modified_duration']:.2f}",
                classification=position["classification"],
                hqla_status=position["hqla_status"],
                mil_status=position["mil_status"],
                recommendation=position["recommendation"],
            )
            for position in portfolio["positions"]
        )
        summary = PortfolioSummary(
            portfolio_name="AIP Core Portfolio",
            valuation_date=portfolio["valuation_date"],
            market_value=f"{portfolio['market_value']:,.2f}",
            book_value=f"{portfolio['book_value']:,.2f}",
            total_positions=len(portfolio["positions"]),
            weighted_yield=f"{portfolio['weighted_yield']:.2f}%",
            modified_duration=f"{portfolio['modified_duration']:.2f}",
            hqla_percent=f"{portfolio['hqla_percent']:.0f}%",
            mil_eligible_percent=f"{portfolio['mil_eligible_percent']:.0f}%",
            currency_distribution=portfolio["currency_distribution"],
        )
        view_model = PortfolioViewModel(
            summary=summary,
            rows=rows,
            filters=filters or {},
            selected_isin=selected_isin,
            theme=theme,
            status="loaded" if not error else "error",
            warnings=("Application workflow returned a warning",) if not loading and not error else (),
            calculation_id=workflow_result["calculation_references"]["portfolio"],
            correlation_id=self._correlation_id,
            loading=loading,
            error=error,
        )
        print(
            f"[portfolio-runtime] presenter view_model summary_total_positions={view_model.summary.total_positions} "
            f"summary_valuation_date={view_model.summary.valuation_date} rows={len(view_model.rows)}"
        )
        return view_model

    def refresh(self, *, theme: str = "light", filters: dict[str, str] | None = None, selected_isin: str | None = None) -> PortfolioViewModel:
        return self.build_view_model(theme=theme, filters=filters, selected_isin=selected_isin)

    def select(self, isin: str | None) -> PortfolioViewModel:
        return self.build_view_model(selected_isin=isin)

    def handle_theme_change(self, theme: str) -> PortfolioViewModel:
        return self.build_view_model(theme=theme)

    def handle_refresh(self) -> PortfolioViewModel:
        return self.build_view_model()

    def apply_filters(self, filters: dict[str, str]) -> PortfolioViewModel:
        return self.build_view_model(filters=filters)

    def handle_application_failure(self, error: str) -> PortfolioViewModel:
        return self.build_view_model(error=error)

    def set_loading(self) -> PortfolioViewModel:
        return self.build_view_model(loading=True)

    def empty_state(self) -> PortfolioViewModel:
        return PortfolioViewModel(
            summary=PortfolioSummary(
                portfolio_name="AIP Core Portfolio",
                valuation_date="2026-07-29",
                market_value="0.00",
                book_value="0.00",
                total_positions=0,
                weighted_yield="0.00%",
                modified_duration="0.00",
                hqla_percent="0%",
                mil_eligible_percent="0%",
                currency_distribution=(),
            ),
            rows=(),
            filters={},
            selected_isin=None,
            theme="light",
            status="empty",
            warnings=(),
            calculation_id="calc-empty",
            correlation_id="corr-empty",
            loading=False,
            error=None,
        )
