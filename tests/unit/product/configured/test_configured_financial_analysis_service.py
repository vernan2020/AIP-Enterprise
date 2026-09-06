from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.readers.sugef_financial_api_client import SUGEFApiReadResult
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


def test_selected_entity_history_enriches_headline_kpis_missing_from_peer_dataset() -> None:
    entity = FinancialEntity("PEER-1", "COOCIQUE")
    cutoff = date(2026, 7, 31)

    def line(
        statement_type: FinancialStatementType,
        account_code: str,
        account_name: str,
        amount: str,
    ) -> FinancialStatementLine:
        return FinancialStatementLine(
            entity=entity,
            statement_date=cutoff,
            statement_type=statement_type,
            account_code=account_code,
            account_name=account_name,
            amount=Decimal(amount),
        )

    reduced_peer_lines = (
        line(FinancialStatementType.BALANCE_SHEET, "10000", "ACTIVO TOTAL", "305281200000"),
        line(
            FinancialStatementType.BALANCE_SHEET,
            "25000",
            "PATRIMONIO TOTAL",
            "45416590000",
        ),
        line(
            FinancialStatementType.INCOME_STATEMENT,
            "30000",
            "RESULTADO FINAL",
            "682520000",
        ),
    )
    complete_selected_lines = (
        line(
            FinancialStatementType.BALANCE_SHEET,
            "11101",
            "CARTERA DE CREDITO",
            "219905750000",
        ),
        line(
            FinancialStatementType.BALANCE_SHEET,
            "20000",
            "PASIVO TOTAL",
            "259864610000",
        ),
    )

    class _PeerReader:
        def read(self, *, cutoff_date: date | None = None) -> SUGEFFinancialReadResult:
            return SUGEFFinancialReadResult(reduced_peer_lines, (), (), "PEER")

        def fingerprint(self, *, cutoff_date: date | None = None) -> str:
            return "PEER"

    class _HistoryReader:
        def read_entity_history(
            self,
            entity_id: str,
            cutoff_date: date,
        ) -> SUGEFApiReadResult:
            assert entity_id == entity.entity_id
            assert cutoff_date == cutoff
            return SUGEFApiReadResult(
                lines=complete_selected_lines,
                endpoints=("SUGEF-HISTORY",),
                diagnostics=(),
            )

    service = ConfiguredFinancialAnalysisService(
        SUGEFFinancialSourceConfig(enabled=True),
        ValuationDateContext(cutoff),
        reader=_PeerReader(),  # type: ignore[arg-type]
        history_reader=_HistoryReader(),  # type: ignore[arg-type]
    )

    snapshot = service.load(selected_entity_id=entity.entity_id, cutoff_date=cutoff)
    metrics = {metric.code: metric for metric in snapshot.metrics}
    history = {series.code: series for series in snapshot.metric_history}

    assert metrics["LOANS"].value == Decimal("219905750000")
    assert metrics["LIABILITIES"].value == Decimal("259864610000")
    assert history["LOANS"].points[-1].value == metrics["LOANS"].value
    assert history["LIABILITIES"].points[-1].value == metrics["LIABILITIES"].value
