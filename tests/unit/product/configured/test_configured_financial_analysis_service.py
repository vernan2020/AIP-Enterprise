from __future__ import annotations

from datetime import date

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.readers.sugef_financial_statement_reader import (
    SUGEFFinancialReadResult,
)
from aip.product.configured.services.configured_financial_analysis_service import (
    ConfiguredFinancialAnalysisService,
)


class _Reader:
    def __init__(self) -> None:
        self.read_count = 0
        self.current_fingerprint = "A"

    def read(self, *, cutoff_date: date | None = None) -> SUGEFFinancialReadResult:
        self.read_count += 1
        return SUGEFFinancialReadResult((), (), (), self.current_fingerprint)

    def fingerprint(self, *, cutoff_date: date | None = None) -> str:
        return self.current_fingerprint


def test_service_reuses_cache_until_source_fingerprint_changes() -> None:
    reader = _Reader()
    service = ConfiguredFinancialAnalysisService(
        SUGEFFinancialSourceConfig(enabled=True, root="C:/SUGEF"),
        ValuationDateContext(date(2026, 7, 31)),
        reader=reader,  # type: ignore[arg-type]
    )

    service.load()
    service.load()
    assert reader.read_count == 1

    reader.current_fingerprint = "B"
    service.load()
    assert reader.read_count == 2


def test_service_does_not_expose_bundled_reference_data_when_sugef_is_disabled() -> None:
    service = ConfiguredFinancialAnalysisService(
        SUGEFFinancialSourceConfig(api_enabled=False),
        ValuationDateContext(date(2026, 7, 30)),
    )

    snapshot = service.load()

    assert snapshot.status == "UNAVAILABLE"
    assert snapshot.cutoff_date == date(2026, 7, 30)
    assert snapshot.selected_entity is None
    assert snapshot.entities == ()
    assert snapshot.statement_lines == ()
    assert snapshot.rating is None
    assert all(metric.value is None for metric in snapshot.metrics)
    assert any("no se utiliza información de respaldo" in item for item in snapshot.diagnostics)
    assert all("referencia institucional" not in item for item in snapshot.diagnostics)
