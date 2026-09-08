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
from aip.product.configured.readers.sugef_financial_history_reader import (
    SUGEFFinancialHistoryReader,
)


class _HistorySpy(SUGEFFinancialHistoryReader):
    def __init__(self) -> None:
        super().__init__(SUGEFFinancialSourceConfig(api_retries=0))
        self.calls: list[tuple[str, str, str, FinancialStatementType]] = []

    def _read_report(
        self,
        entity_code: str,
        period: str,
        report_name: str,
        list_key: str,
        statement_type: FinancialStatementType,
    ) -> tuple[list[FinancialStatementLine], str]:
        self.calls.append((entity_code, period, report_name, statement_type))
        return (
            [
                FinancialStatementLine(
                    entity=FinancialEntity(entity_code, "Entidad histórica"),
                    statement_date=date(2026, 7, 31),
                    statement_type=statement_type,
                    account_code="TEST",
                    account_name="Dato histórico",
                    amount=Decimal("1"),
                )
            ],
            f"https://sugef.example/{list_key}",
        )


def test_history_reader_requests_three_reports_for_selected_entity_only() -> None:
    reader = _HistorySpy()

    result = reader.read_entity_history("3004045138", date(2026, 7, 31))

    assert len(reader.calls) == 3
    assert {call[0] for call in reader.calls} == {"3004045138"}
    assert {call[1] for call in reader.calls} == {"20240901-20260701"}
    assert {call[3] for call in reader.calls} == {
        FinancialStatementType.BALANCE_SHEET,
        FinancialStatementType.INCOME_STATEMENT,
        FinancialStatementType.INDICATORS,
    }
    assert len(result.lines) == 3
    assert all(line.entity.entity_id == "3004045138" for line in result.lines)
    assert any("consulta acotada a una entidad" in message for message in result.diagnostics)
    assert any("23 meses" in message for message in result.diagnostics)


def test_history_reader_does_not_call_api_when_disabled() -> None:
    reader = SUGEFFinancialHistoryReader(
        SUGEFFinancialSourceConfig(api_enabled=False, api_retries=0)
    )

    result = reader.read_entity_history("3004045138", date(2026, 7, 31))

    assert result.lines == ()
    assert any("API pública deshabilitada" in message for message in result.diagnostics)
