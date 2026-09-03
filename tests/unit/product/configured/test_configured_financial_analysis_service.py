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

    def read(self) -> SUGEFFinancialReadResult:
        self.read_count += 1
        return SUGEFFinancialReadResult((), (), (), self.current_fingerprint)

    def fingerprint(self) -> str:
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
