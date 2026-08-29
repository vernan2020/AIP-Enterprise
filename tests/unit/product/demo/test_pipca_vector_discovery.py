from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.configured.adapters.pipca_vector_reader import InstitutionalVectorReader
from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
    FolderWatchSourceConfig,
)
from aip.product.demo.configuration.demo_config import DemoConfig


def _build_provider(
    tmp_path: Path, *, data_cutoff_date: date = date(2026, 7, 29), allow_prior: bool = False
) -> ConfiguredPortfolioProvider:
    config = DemoConfig(
        execution_mode="CONFIGURED", demo_mode_enabled=False, data_cutoff_date=data_cutoff_date
    )
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(
            enabled=True, portfolio_root=str(tmp_path / "institutional")
        ),
        metadata={
            "allow_prior_source_date": allow_prior,
            "data_cutoff_date": data_cutoff_date.isoformat(),
        },
    )
    return ConfiguredPortfolioProvider(config, source_config)


def test_discovery_selects_exact_pipca_txt_vector(tmp_path: Path) -> None:
    root = tmp_path / "institutional" / "Inversiones" / "2026"
    (root / "vector").mkdir(parents=True)
    (root / "maestro").mkdir(parents=True)
    (root / "maestro" / "29-07-2026.xls").write_text("x")
    (root / "vector" / "VectorPiPCA_20260729.txt").write_text(
        "row_id;instrument_id;price;valuation_date\n1;ABC;1000.25;2026-07-29\n", encoding="utf-8"
    )
    (root / "vector" / "COOPEALIANZA_SUGEF_20260731.xls").write_text("x")

    provider = _build_provider(tmp_path)
    payload = provider.get_portfolio()

    assert payload["price_vector"]["status"] == "HEALTHY"
    assert payload["price_vector"]["file_name"] == "VectorPiPCA_20260729.txt"
    assert payload["price_vector"]["valuation_date"] == "2026-07-29"
    assert payload["price_vector"]["directory"] == str(root / "vector")


def test_discovery_matches_case_insensitive_pipca_prefix(tmp_path: Path) -> None:
    root = tmp_path / "institutional" / "Inversiones" / "2026"
    (root / "vector").mkdir(parents=True)
    (root / "vector" / "vectorpipca_20260729.txt").write_text(
        "row_id;instrument_id;price;valuation_date\n1;ABC;1000.25;2026-07-29\n", encoding="utf-8"
    )

    provider = _build_provider(tmp_path)
    payload = provider.get_portfolio()

    assert payload["price_vector"]["status"] == "HEALTHY"
    assert payload["price_vector"]["file_name"] == "vectorpipca_20260729.txt"


def test_discovery_excludes_sugef_and_other_unrelated_files(tmp_path: Path) -> None:
    root = tmp_path / "institutional" / "Inversiones" / "2026"
    (root / "vector").mkdir(parents=True)
    (root / "vector" / "COOPEALIANZA_SUGEF_20260731.xls").write_text("x")
    (root / "vector" / "VectorPiPCA_20260728.txt").write_text(
        "row_id;instrument_id;price;valuation_date\n1;ABC;1000.25;2026-07-28\n", encoding="utf-8"
    )

    provider = _build_provider(tmp_path, allow_prior=True)
    payload = provider.get_portfolio()

    assert payload["price_vector"]["status"] == "DEGRADED"
    assert payload["price_vector"]["file_name"] == "VectorPiPCA_20260728.txt"
    assert "COOPEALIANZA_SUGEF_20260731.xls" not in payload["price_vector"]["file_name"]


def test_discovery_falls_back_to_prior_pipca_vector_when_allowed(tmp_path: Path) -> None:
    root = tmp_path / "institutional" / "Inversiones" / "2026"
    (root / "vector").mkdir(parents=True)
    (root / "vector" / "VectorPiPCA_20260728.txt").write_text(
        "row_id;instrument_id;price;valuation_date\n1;ABC;1000.25;2026-07-28\n", encoding="utf-8"
    )

    provider = _build_provider(tmp_path, allow_prior=True)
    payload = provider.get_portfolio()

    assert payload["price_vector"]["status"] == "DEGRADED"
    assert payload["price_vector"]["file_name"] == "VectorPiPCA_20260728.txt"
    assert payload["price_vector"]["valuation_date"] == "2026-07-28"


def test_discovery_rejects_future_pipca_vectors(tmp_path: Path) -> None:
    root = tmp_path / "institutional" / "Inversiones" / "2026"
    (root / "vector").mkdir(parents=True)
    (root / "vector" / "VectorPiPCA_20260801.txt").write_text(
        "row_id;instrument_id;price;valuation_date\n1;ABC;1000.25;2026-08-01\n", encoding="utf-8"
    )

    provider = _build_provider(tmp_path)
    payload = provider.get_portfolio()

    assert payload["price_vector"]["status"] == "UNAVAILABLE"


def test_discovery_marks_duplicate_pipca_candidates_as_degraded(tmp_path: Path) -> None:
    root = tmp_path / "institutional" / "Inversiones" / "2026"
    (root / "vector").mkdir(parents=True)
    (root / "vector" / "VectorPiPCA_20260729.txt").write_text(
        "row_id;instrument_id;price;valuation_date\n1;ABC;1000.25;2026-07-29\n", encoding="utf-8"
    )
    (root / "vector" / "VectorPiPCA_20260729.TXT").write_text(
        "row_id;instrument_id;price;valuation_date\n2;ABC;1000.25;2026-07-29\n", encoding="utf-8"
    )

    provider = _build_provider(tmp_path)
    payload = provider.get_portfolio()

    assert payload["price_vector"]["status"] == "DEGRADED"
    assert payload["price_vector"]["diagnostics"]["candidate_count"] == 2


def test_aligned_master_and_vector_dates_for_verified_case(tmp_path: Path) -> None:
    root = tmp_path / "institutional" / "Inversiones" / "2026"
    (root / "maestro").mkdir(parents=True)
    (root / "vector").mkdir(parents=True)
    (root / "maestro" / "29-07-2026.xls").write_text("x")
    (root / "vector" / "VectorPiPCA_20260729.txt").write_text(
        "row_id;instrument_id;price;valuation_date\n1;ABC;1000.25;2026-07-29\n", encoding="utf-8"
    )

    provider = _build_provider(tmp_path)
    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["valuation_date"] == "2026-07-29"
    assert payload["price_vector"]["valuation_date"] == "2026-07-29"


def test_pipca_txt_reader_parses_semicolon_delimited_rows(tmp_path: Path) -> None:
    path = tmp_path / "VectorPiPCA_20260729.txt"
    path.write_text(
        "row_id;instrument_id;price;valuation_date\nA-1;ABC;1.250,40;2026-07-29\n",
        encoding="cp1252",
    )

    rows = InstitutionalVectorReader().read(path)

    assert len(rows) == 1
    assert rows[0].row_id == "A-1"
    assert rows[0].instrument_id == "ABC"
    assert rows[0].price == pytest.approx(1250.4)
    assert rows[0].valuation_date == date(2026, 7, 29)


def test_pipca_txt_reader_rejects_malformed_rows(tmp_path: Path) -> None:
    path = tmp_path / "VectorPiPCA_20260729.txt"
    path.write_text(
        "row_id;instrument_id;price;valuation_date\nA-1;ABC;not-a-number;2026-07-29\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="malformed"):
        InstitutionalVectorReader().read(path)


def test_environment_loader_reads_vector_patterns_and_extensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIP_EXECUTION_MODE", "CONFIGURED")
    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "false")
    monkeypatch.setenv("AIP_VECTOR_ENABLED", "true")
    monkeypatch.setenv("AIP_VECTOR_FILE_PATTERNS", "VectorPiPCA_{yyyymmdd}.txt")
    monkeypatch.setenv("AIP_VECTOR_SUPPORTED_EXTENSIONS", ".txt,.xls,.xlsx")

    from aip.product.demo.configuration.environment_loader import EnvironmentLoader

    config = EnvironmentLoader().load()
    vector_config = config.source_config["vector"]

    assert vector_config["file_pattern"] == "VectorPiPCA_{yyyymmdd}.txt"
    assert vector_config["supported_extensions"] == [".txt", ".xls", ".xlsx"]
