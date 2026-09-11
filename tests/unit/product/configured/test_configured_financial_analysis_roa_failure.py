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
from aip.product.configured.readers.sugef_financial_statement_reader import (
    SUGEFFinancialReadResult,
)
from aip.product.configured.services.configured_financial_analysis_service import (
    ConfiguredFinancialAnalysisService,
)


def test_history_failure_does_not_fall_back_to_published_or_point_in_time_roa() -> None:
    entity = FinancialEntity("7", "Coopealianza R.L.")
    cutoff = date(2026, 7, 31)
    lines = (
        FinancialStatementLine(
            entity=entity,
            statement_date=cutoff,
            statement_type=FinancialStatementType.BALANCE_SHEET,
            account_code="10000",
            account_name="ACTIVO TOTAL",
            amount=Decimal("800000000000"),
        ),
        FinancialStatementLine(
            entity=entity,
            statement_date=cutoff,
            statement_type=FinancialStatementType.INCOME_STATEMENT,
            account_code="30000",
            account_name="RESULTADO FINAL",
            amount=Decimal("8000000000"),
        ),
        FinancialStatementLine(
            entity=entity,
            statement_date=cutoff,
            statement_type=FinancialStatementType.INDICATORS,
            account_code="81000",
            account_name="ROA",
            amount=Decimal("0.0125"),
        ),
    )

    class _Reader:
        def read(self, *, cutoff_date: date | None = None) -> SUGEFFinancialReadResult:
            return SUGEFFinancialReadResult(lines, (), (), "ROA")

        def fingerprint(self, *, cutoff_date: date | None = None) -> str:
            return "ROA"

    class _FailingHistoryReader:
        def read_entity_history(self, entity_id: str, cutoff_date: date):
            raise RuntimeError("history unavailable")

    service = ConfiguredFinancialAnalysisService(
        SUGEFFinancialSourceConfig(enabled=True),
        ValuationDateContext(cutoff),
        reader=_Reader(),  # type: ignore[arg-type]
        history_reader=_FailingHistoryReader(),  # type: ignore[arg-type]
    )

    snapshot = service.load(selected_entity_id=entity.entity_id, cutoff_date=cutoff)
    roa = next(metric for metric in snapshot.metrics if metric.code == "ROA")

    assert roa.value is None
    assert roa.previous_value is None
    assert roa.change_percent is None
    assert roa.source_account is not None
    assert "promedio últimos 12 meses" in roa.source_account
    assert any("ROA permanece N/D" in item for item in snapshot.diagnostics)
