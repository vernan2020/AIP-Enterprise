from __future__ import annotations

from calendar import monthrange
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
from aip.product.configured.readers.sugef_official_financial_api_client import (
    SUGEFOfficialFinancialApiClient,
)

CUTOFF = date(2026, 7, 31)
PRIMARY = "3004045138"
PEER_1 = "3004000001"
PEER_2 = "3004000002"


class _PeerRecoverySpyClient(SUGEFOfficialFinancialApiClient):
    def __init__(self) -> None:
        super().__init__(
            SUGEFFinancialSourceConfig(
                api_retries=0,
                api_entity_codes=(PRIMARY,),
            )
        )
        self.filtered_jobs: list[tuple[str, str, str, str, FinancialStatementType, str]] = []

    def _execute_filtered_jobs(
        self,
        jobs: list[tuple[str, str, str, str, FinancialStatementType, str]],
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        self.filtered_jobs.extend(jobs)


def _line(
    entity_code: str,
    statement_date: date,
    statement_type: FinancialStatementType,
    *,
    account_code: str,
    account_name: str,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=FinancialEntity(entity_code, f"Entidad {entity_code}"),
        statement_date=statement_date,
        statement_type=statement_type,
        account_code=account_code,
        account_name=account_name,
        amount=Decimal("1"),
    )


def _indicator(entity_code: str) -> FinancialStatementLine:
    return _line(
        entity_code,
        CUTOFF,
        FinancialStatementType.INDICATORS,
        account_code="81000",
        account_name="ROA",
    )


def test_peer_history_recovery_requests_only_missing_discovered_sugef_peers() -> None:
    client = _PeerRecoverySpyClient()
    lines = [_indicator(PEER_1), _indicator(PEER_2), _indicator(PRIMARY)]
    diagnostics: list[str] = []

    client._recover_incomplete_peer_history(CUTOFF, lines, set(), diagnostics)

    balance_period = client._period_range(
        CUTOFF,
        lookback_months=client._AVERAGE_LOOKBACK_MONTHS,
    )
    income_period = client._result_periods(CUTOFF)

    expected: set[tuple[str, str, FinancialStatementType, str]] = set()
    for peer in (PEER_1, PEER_2):
        expected.update(
            (peer, balance_period, FinancialStatementType.BALANCE_SHEET, account)
            for account in client._METHODOLOGY_BALANCE_ACCOUNTS
        )
        expected.update(
            (peer, income_period, FinancialStatementType.INCOME_STATEMENT, account)
            for account in client._METHODOLOGY_INCOME_ACCOUNTS
        )

    assert {
        (entity_code, period, statement_type, account_code)
        for entity_code, period, _report, _list_key, statement_type, account_code in client.filtered_jobs
    } == expected
    assert all(job[0] != PRIMARY for job in client.filtered_jobs)
    assert any("0/2 entidades" in message for message in diagnostics)


def test_methodology_history_requires_exact_methodology_accounts_and_periods() -> None:
    lines: list[FinancialStatementLine] = []
    start = date(2025, 8, 1)
    for offset in range(12):
        month = SUGEFOfficialFinancialApiClient._shift_month(start, offset)
        month_end = date(month.year, month.month, monthrange(month.year, month.month)[1])
        lines.extend(
            (
                _line(
                    PEER_1,
                    month_end,
                    FinancialStatementType.BALANCE_SHEET,
                    account_code="10000",
                    account_name="ACTIVO TOTAL",
                ),
                _line(
                    PEER_1,
                    month_end,
                    FinancialStatementType.BALANCE_SHEET,
                    account_code="25000",
                    account_name="PATRIMONIO TOTAL",
                ),
            )
        )

    required_result_dates = (
        date(2025, 7, 31),
        date(2025, 12, 31),
        CUTOFF,
    )
    account_names = {
        "30000": "RESULTADO FINAL",
        "31000": "RESULTADO OPERACIONAL BRUTO",
        "31300": "RESULTADO INTERMEDIACION FINANCIERA",
        "32000": "GASTOS DE ADMINISTRACION",
    }
    for account_code, account_name in account_names.items():
        for result_date in required_result_dates:
            lines.append(
                _line(
                    PEER_1,
                    result_date,
                    FinancialStatementType.INCOME_STATEMENT,
                    account_code=account_code,
                    account_name=account_name,
                )
            )

    assert SUGEFOfficialFinancialApiClient._has_methodology_history(
        lines,
        PEER_1,
        CUTOFF,
    )

    without_admin_expense = [line for line in lines if line.account_code != "32000"]
    assert not SUGEFOfficialFinancialApiClient._has_methodology_history(
        without_admin_expense,
        PEER_1,
        CUTOFF,
    )
