from __future__ import annotations

from datetime import date
from decimal import Decimal

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


def test_service_exposes_reference_data_for_july_cutoff() -> None:
    service = ConfiguredFinancialAnalysisService(
        SUGEFFinancialSourceConfig(),
        ValuationDateContext(date(2026, 7, 30)),
    )

    snapshot = service.load()

    assert snapshot.status == "PARTIAL"
    assert snapshot.cutoff_date == date(2026, 7, 30)
    assert snapshot.selected_entity is not None
    assert snapshot.selected_entity.name == "COOPEALIANZA R.L."
    assert len(snapshot.entities) == 38
    assert len(snapshot.statement_lines) == 13
    assert snapshot.rating is not None
    assert snapshot.rating.status == "COMPLETE"
    assert snapshot.rating.coverage_percent == 100
    metrics = {item.code: item.value for item in snapshot.metrics}
    assert metrics["LOANS"] is None
    assert metrics["ROA"] is not None and metrics["ROA"].quantize(Decimal("0.01")) == Decimal("1.04")
    assert metrics["ROE"] is not None and metrics["ROE"].quantize(Decimal("0.01")) == Decimal("5.74")
    assert any("falta el Balance" in item for item in snapshot.diagnostics)
    assert any("falta el Estado de Resultados" in item for item in snapshot.diagnostics)
