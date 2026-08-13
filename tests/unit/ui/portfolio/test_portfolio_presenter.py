from __future__ import annotations

from datetime import date

import openpyxl

from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig, FolderWatchSourceConfig
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel
from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView

from aip.product.configured.adapters.configured_portfolio_provider import ConfiguredPortfolioProvider


class FakeWorkflow:
    def __init__(self, payloads: tuple[dict[str, object], ...]) -> None:
        self._payloads = list(payloads)
        self._call_count = 0

    def execute(self, correlation_id: str) -> dict[str, object]:
        payload = self._payloads[self._call_count % len(self._payloads)]
        self._call_count += 1
        return {
            "correlation_id": correlation_id,
            "calculation_references": {"portfolio": "calc-portfolio"},
            "portfolio": payload,
        }


class FakeApplicationFactory:
    def __init__(self, payloads: tuple[dict[str, object], ...]) -> None:
        self._payloads = payloads
        self._workflow = FakeWorkflow(self._payloads)

    def initial_load_workflow(self) -> FakeWorkflow:
        return self._workflow


def test_presenter_builds_immutable_view_model() -> None:
    payload = {
        "valuation_date": "2026-07-29",
        "market_value": 100.0,
        "book_value": 90.0,
        "weighted_yield": 2.5,
        "modified_duration": 1.2,
        "hqla_percent": 50.0,
        "mil_eligible_percent": 60.0,
        "currency_distribution": ("USD",),
        "positions": [
            {
                "isin": "US0000001",
                "issuer": "Issuer One",
                "instrument": "Bond",
                "currency": "USD",
                "nominal": 1000.0,
                "market_value": 100.0,
                "book_value": 90.0,
                "yield_value": 2.5,
                "modified_duration": 1.2,
                "classification": "Govt",
                "hqla_status": "Eligible",
                "mil_status": "Eligible",
                "recommendation": "Hold",
            }
        ],
    }
    presenter = PortfolioPresenter(FakeApplicationFactory((payload,)))
    view_model = presenter.build_view_model(theme="dark")

    assert isinstance(view_model, PortfolioViewModel)
    assert view_model.theme == "dark"
    assert view_model.summary.portfolio_name == "AIP Core Portfolio"
    assert view_model.rows[0].isin == "US0000001"


def test_presenter_handles_filters_and_selection() -> None:
    payload = {
        "valuation_date": "2026-07-29",
        "market_value": 100.0,
        "book_value": 90.0,
        "weighted_yield": 2.5,
        "modified_duration": 1.2,
        "hqla_percent": 50.0,
        "mil_eligible_percent": 60.0,
        "currency_distribution": ("USD",),
        "positions": [
            {
                "isin": "US0000001",
                "issuer": "Issuer One",
                "instrument": "Bond",
                "currency": "USD",
                "nominal": 1000.0,
                "market_value": 100.0,
                "book_value": 90.0,
                "yield_value": 2.5,
                "modified_duration": 1.2,
                "classification": "Govt",
                "hqla_status": "Eligible",
                "mil_status": "Eligible",
                "recommendation": "Hold",
            }
        ],
    }
    presenter = PortfolioPresenter(FakeApplicationFactory((payload,)))
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


def test_configured_provider_yield_reaches_presenter_summary(tmp_path, qt_app) -> None:
    root = tmp_path / "institutional"
    maestro_dir = root / "Inversiones" / "2026" / "maestro" / "julio"
    vector_dir = root / "Inversiones" / "2026" / "vector" / "julio"
    maestro_dir.mkdir(parents=True)
    vector_dir.mkdir(parents=True)

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Maestro"
    worksheet.append(["Resumen institucional", ""])
    worksheet.append(["", ""])
    worksheet.append(["ISIN", "Emisor", "Valor de Mercado", "Valor Mercado Colonizado", "Valor en Libros", "TIR", "Tasa Nominal"])
    worksheet.append(["US0000001", "Issuer One", 1000000, 1000000, 980000, 5.0, 4.0])
    worksheet.append(["US0000002", "Issuer Two", 2000000, 2000000, 1960000, 0.0, 4.0])
    workbook.save(maestro_dir / "29-07-2026.xlsx")
    (vector_dir / "29-07-2026.txt").write_text(
        "BCCR  BC12M120826 12/08/2026  100.0 100.008344  2.842 0.000000 0\n",
        encoding="utf-8",
    )

    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False, data_cutoff_date=date(2026, 7, 29))
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root), vector_path=str(vector_dir)),
    )
    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()

    presenter = PortfolioPresenter(FakeApplicationFactory((payload,)))
    view_model = presenter.build_view_model()

    assert payload["weighted_yield"] == 4.333333333333333
    assert view_model.summary.weighted_yield == "4.33%"


def test_configured_provider_payload_reaches_presenter_and_table_model(tmp_path, qt_app) -> None:
    root = tmp_path / "institutional"
    maestro_dir = root / "Inversiones" / "2026" / "maestro" / "julio"
    vector_dir = root / "Inversiones" / "2026" / "vector" / "julio"
    maestro_dir.mkdir(parents=True)
    vector_dir.mkdir(parents=True)

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Maestro"
    worksheet.append(["Resumen institucional", ""])
    worksheet.append(["", ""])
    worksheet.append(["ISIN", "Emisor", "Valor de Mercado", "Valor en Libros"])
    worksheet.append(["US0000001", "Issuer One", 1000000, 980000])
    worksheet.append(["US0000002", "Issuer Two", 2000000, 1960000])
    workbook.save(maestro_dir / "29-07-2026.xlsx")
    (vector_dir / "29-07-2026.txt").write_text(
        "BCCR  BC12M120826 12/08/2026  100.0 100.008344  2.842 0.000000 0\n",
        encoding="utf-8",
    )

    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False, data_cutoff_date=date(2026, 7, 29))
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root), vector_path=str(vector_dir)),
    )
    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()

    assert len(payload["positions"]) == 2

    presenter = PortfolioPresenter(FakeApplicationFactory((payload,)))
    view = PortfolioView(presenter=presenter)

    assert view.view_model().summary.total_positions == 2
    assert view._positions._table.rowCount() == 2


def test_refresh_action_rebinds_view_model_and_table_rows(qt_app) -> None:
    payloads = (
        {
            "valuation_date": "2026-07-29",
            "market_value": 100.0,
            "book_value": 90.0,
            "weighted_yield": 2.5,
            "modified_duration": 1.2,
            "hqla_percent": 50.0,
            "mil_eligible_percent": 60.0,
            "currency_distribution": ("USD",),
            "positions": [
                {
                    "isin": "US0000001",
                    "issuer": "Issuer One",
                    "instrument": "Bond",
                    "currency": "USD",
                    "nominal": 1000.0,
                    "market_value": 100.0,
                    "book_value": 90.0,
                    "yield_value": 2.5,
                    "modified_duration": 1.2,
                    "classification": "Govt",
                    "hqla_status": "Eligible",
                    "mil_status": "Eligible",
                    "recommendation": "Hold",
                }
            ],
        },
        {
            "valuation_date": "2026-07-29",
            "market_value": 200.0,
            "book_value": 180.0,
            "weighted_yield": 3.5,
            "modified_duration": 1.7,
            "hqla_percent": 60.0,
            "mil_eligible_percent": 70.0,
            "currency_distribution": ("USD",),
            "positions": [
                {
                    "isin": "US0000001",
                    "issuer": "Issuer One",
                    "instrument": "Bond",
                    "currency": "USD",
                    "nominal": 1000.0,
                    "market_value": 100.0,
                    "book_value": 90.0,
                    "yield_value": 2.5,
                    "modified_duration": 1.2,
                    "classification": "Govt",
                    "hqla_status": "Eligible",
                    "mil_status": "Eligible",
                    "recommendation": "Hold",
                },
                {
                    "isin": "US0000002",
                    "issuer": "Issuer Two",
                    "instrument": "Bond",
                    "currency": "USD",
                    "nominal": 2000.0,
                    "market_value": 200.0,
                    "book_value": 180.0,
                    "yield_value": 3.5,
                    "modified_duration": 1.7,
                    "classification": "Govt",
                    "hqla_status": "Eligible",
                    "mil_status": "Eligible",
                    "recommendation": "Hold",
                },
            ],
        },
    )

    presenter = PortfolioPresenter(FakeApplicationFactory(payloads))
    view = PortfolioView(presenter=presenter)

    assert view.view_model().summary.total_positions == 1
    assert view._positions._table.rowCount() == 1

    refresh_action = view._toolbar.actions()[0]
    refresh_action.trigger()

    assert view.view_model().summary.total_positions == 2
    assert view._positions._table.rowCount() == 2
