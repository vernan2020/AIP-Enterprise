from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from aip.product.configured.adapters.configured_portfolio_provider import ConfiguredPortfolioProvider
from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig, FolderWatchSourceConfig
from aip.product.demo.configuration.demo_config import DemoConfig


def _create_provider(tmp_path: Path, *, cutoff_date: date, portfolio_root: Path | None = None, allow_prior: bool = False) -> tuple[ConfiguredPortfolioProvider, Path]:
    root = portfolio_root or tmp_path / "institutional"
    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False, data_cutoff_date=cutoff_date)
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root)),
        metadata={"allow_prior_source_date": allow_prior},
    )
    provider = ConfiguredPortfolioProvider(config, source_config)
    return provider, root


@pytest.mark.parametrize("month_index, month_name", [(1, "enero"), (2, "febrero"), (3, "marzo"), (4, "abril"), (5, "mayo"), (6, "junio"), (7, "julio"), (8, "agosto"), (9, "setiembre"), (10, "octubre"), (11, "noviembre"), (12, "diciembre")])
def test_portfolio_master_discovery_supports_all_twelve_spanish_month_directories(tmp_path: Path, month_index: int, month_name: str) -> None:
    cutoff_date = date(2026, month_index, 15)
    provider, root = _create_provider(tmp_path, cutoff_date=cutoff_date)
    month_dir = root / "Inversiones" / "2026" / "maestro" / month_name
    month_dir.mkdir(parents=True)
    (month_dir / f"15-{month_index:02d}-2026.xls").write_text("x")

    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "HEALTHY"
    assert payload["portfolio_master"]["directory"] == str(month_dir)
    assert payload["portfolio_master"]["valuation_date"] == cutoff_date.isoformat()


@pytest.mark.parametrize("month_dir_name", ["setiembre", "septiembre", "SEPTIEMBRE", "  seTiEmbre  "])
def test_portfolio_master_discovery_accepts_month_aliases_and_case_insensitive_names(tmp_path: Path, month_dir_name: str) -> None:
    cutoff_date = date(2026, 9, 15)
    provider, root = _create_provider(tmp_path, cutoff_date=cutoff_date)
    month_dir = root / "Inversiones" / "2026" / "maestro" / month_dir_name
    month_dir.mkdir(parents=True)
    (month_dir / "15-09-2026.xls").write_text("x")

    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "HEALTHY"
    assert payload["portfolio_master"]["file_name"] == "15-09-2026.xls"
    assert payload["portfolio_master"]["valuation_date"] == cutoff_date.isoformat()


def test_exact_cutoff_searches_only_the_target_month_directory_for_master_and_vector(tmp_path: Path) -> None:
    provider, root = _create_provider(tmp_path, cutoff_date=date(2026, 7, 29))
    july_master_dir = root / "Inversiones" / "2026" / "maestro" / "julio"
    july_master_dir.mkdir(parents=True)
    (july_master_dir / "29-07-2026.xls").write_text("x")
    april_master_dir = root / "Inversiones" / "2026" / "maestro" / "abril"
    april_master_dir.mkdir(parents=True)
    (april_master_dir / "29-07-2026.xls").write_text("x")

    vector_dir = root / "Inversiones" / "2026" / "vector" / "julio"
    vector_dir.mkdir(parents=True)
    (vector_dir / "29-07-2026.xlsx").write_text("x")
    other_vector_dir = root / "Inversiones" / "2026" / "vector" / "abril"
    other_vector_dir.mkdir(parents=True)
    (other_vector_dir / "29-07-2026.xlsx").write_text("x")

    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "HEALTHY"
    assert payload["portfolio_master"]["directory"] == str(july_master_dir)
    assert payload["portfolio_master"]["file_name"] == "29-07-2026.xls"
    assert payload["price_vector"]["status"] == "HEALTHY"
    assert payload["price_vector"]["directory"] == str(vector_dir)
    assert payload["price_vector"]["file_name"] == "29-07-2026.xlsx"


def test_missing_exact_cutoff_returns_unavailable_when_prior_fallback_is_disabled(tmp_path: Path) -> None:
    provider, root = _create_provider(tmp_path, cutoff_date=date(2026, 7, 29), allow_prior=False)
    month_dir = root / "Inversiones" / "2026" / "maestro" / "julio"
    month_dir.mkdir(parents=True)
    (month_dir / "28-07-2026.xls").write_text("x")

    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "UNAVAILABLE"
    assert payload["portfolio_master"]["file_name"] is None


def test_prior_date_fallback_is_enabled_for_same_month_and_marks_source_degraded(tmp_path: Path) -> None:
    provider, root = _create_provider(tmp_path, cutoff_date=date(2026, 7, 29), allow_prior=True)
    month_dir = root / "Inversiones" / "2026" / "maestro" / "julio"
    month_dir.mkdir(parents=True)
    (month_dir / "28-07-2026.xls").write_text("x")

    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "DEGRADED"
    assert payload["portfolio_master"]["file_name"] == "28-07-2026.xls"
    assert payload["portfolio_master"]["valuation_date"] == "2026-07-28"
    assert payload["portfolio_master"]["diagnostics"]["selected_prior_date"] == "2026-07-28"


def test_prior_fallback_does_not_use_future_dates(tmp_path: Path) -> None:
    provider, root = _create_provider(tmp_path, cutoff_date=date(2026, 7, 29), allow_prior=True)
    month_dir = root / "Inversiones" / "2026" / "maestro" / "julio"
    month_dir.mkdir(parents=True)
    (month_dir / "30-07-2026.xls").write_text("x")

    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "UNAVAILABLE"
    assert payload["portfolio_master"]["file_name"] is None


def test_prior_fallback_does_not_cross_into_other_years(tmp_path: Path) -> None:
    provider, root = _create_provider(tmp_path, cutoff_date=date(2026, 7, 29), allow_prior=True)
    month_dir = root / "Inversiones" / "2026" / "maestro" / "julio"
    month_dir.mkdir(parents=True)
    (month_dir / "31-12-2025.xls").write_text("x")

    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "UNAVAILABLE"
    assert payload["portfolio_master"]["file_name"] is None


def test_portfolio_discovery_supports_windows_paths_with_spaces(tmp_path: Path) -> None:
    root = tmp_path / "Root With Spaces"
    provider, _ = _create_provider(tmp_path, cutoff_date=date(2026, 7, 29), portfolio_root=root)
    month_dir = root / "Inversiones" / "2026" / "maestro" / "julio"
    month_dir.mkdir(parents=True)
    (month_dir / "29-07-2026.xls").write_text("x")

    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "HEALTHY"
    assert payload["portfolio_master"]["file_name"] == "29-07-2026.xls"


def test_configured_provider_does_not_fall_back_to_demo_when_sources_are_missing(tmp_path: Path) -> None:
    provider, root = _create_provider(tmp_path, cutoff_date=date(2026, 7, 29), allow_prior=False)
    assert not (root / "Inversiones" / "2026" / "maestro").exists()

    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "UNAVAILABLE"
    assert payload["portfolio_master"]["file_name"] is None
    assert payload["price_vector"]["status"] == "UNAVAILABLE"
