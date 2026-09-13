from __future__ import annotations

from datetime import date
from pathlib import Path

from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
    FolderWatchSourceConfig,
)
from aip.product.configured.services.configured_portfolio_history_service import (
    ConfiguredPortfolioHistoryService,
    PortfolioKPIHistoryResult,
)
from aip.product.demo.configuration.demo_config import DemoConfig


def _service(tmp_path: Path) -> tuple[ConfiguredPortfolioHistoryService, Path]:
    root = tmp_path / "institutional"
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root))
    )
    return (
        ConfiguredPortfolioHistoryService(
            DemoConfig(
                execution_mode="CONFIGURED",
                demo_mode_enabled=False,
                data_cutoff_date=date(2026, 7, 31),
            ),
            source_config,
        ),
        root,
    )


def test_history_discovery_uses_only_parseable_institutional_master_cuts(tmp_path: Path) -> None:
    service, root = _service(tmp_path)
    january = root / "Inversiones" / "2026" / "maestro" / "enero"
    february = root / "Inversiones" / "2026" / "maestro" / "febrero"
    january.mkdir(parents=True)
    february.mkdir(parents=True)
    (january / "15-01-2026.xls").write_text("x")
    (january / "31-01-2026.xlsx").write_text("x")
    (january / "31-01-2026 copia.xlsx").write_text("x")
    (february / "20260228.txt").write_text("x")
    (february / "notas.xlsx").write_text("x")

    dates = service._discover_available_dates(  # noqa: SLF001 - source discovery contract
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 28),
    )

    assert dates == (
        date(2026, 1, 15),
        date(2026, 1, 31),
        date(2026, 2, 28),
    )


def test_monthly_sampling_selects_latest_available_cut_per_month() -> None:
    values = (
        date(2026, 1, 15),
        date(2026, 1, 31),
        date(2026, 2, 14),
        date(2026, 2, 28),
        date(2026, 3, 31),
    )

    sampled = ConfiguredPortfolioHistoryService._sample_dates(  # noqa: SLF001
        values,
        sampling="monthly",
    )

    assert sampled == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]


def test_daily_sampling_preserves_every_available_cut() -> None:
    values = (date(2026, 1, 15), date(2026, 1, 31), date(2026, 2, 28))

    sampled = ConfiguredPortfolioHistoryService._sample_dates(  # noqa: SLF001
        values,
        sampling="daily",
    )

    assert sampled == list(values)


def test_cache_clear_rejects_result_from_older_generation(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    cache_key = (None, date(2026, 7, 31), "monthly", 96)
    stale_generation = service._cache_generation  # noqa: SLF001 - concurrency contract
    result = PortfolioKPIHistoryResult(points=(), status="HEALTHY")

    service.clear_cache()
    service._cache_if_current(  # noqa: SLF001 - concurrency contract
        cache_key,
        result,
        generation=stale_generation,
    )

    assert cache_key not in service._cache  # noqa: SLF001 - concurrency contract
