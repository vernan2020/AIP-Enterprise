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
        self.executed_jobs: list[tuple[str, str, str, str, FinancialStatementType]] = []

    def _execute_jobs(
        self,
        jobs: list[tuple[str, str, str, str, FinancialStatementType]],
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        self.executed_jobs.extend(jobs)


def _line(
    entity_code: str,
    statement_date: date,
    statement_type: FinancialStatementType,
    *,
    account_name: str,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=FinancialEntity(entity_code, f"Entidad {entity_code}"),
        statement_date=statement_date,
        statement_type=statement_type,
        account_code="TEST",
        account_name=account_name,
        amount=Decimal("1"),
    )


def test_peer_history_recovery_requests_only_missing_discovered_sugef_peers() -> None:
    client = _PeerRecoverySpyClient()
    lines = [
        _line(
            PEER_1,
            CUTOFF,
            FinancialStatementType.INDICATORS,
            account_name="ROA",
        ),
        _line(
            PEER_2,
            CUTOFF,
            FinancialStatementType.INDICATORS,
            account_name="ROA",
        ),
        _line(
            PRIMARY,
            CUTOFF,
            FinancialStatementType.INDICATORS,
            account_name="ROA",
        ),
    ]
    diagnostics: list[str] = []

    client._recover_incomplete_peer_history(CUTOFF, lines, set(), diagnostics)

    balance_period = client._period_range(
        CUTOFF,
        lookback_months=client._AVERAGE_LOOKBACK_MONTHS,
    )
    income_period = client._result_periods(CUTOFF)
    assert {
        (entity_code, period, statement_type)
        for entity_code, period, _report, _list_key, statement_type in client.executed_jobs
    } == {
        (PEER_1, balance_period, FinancialStatementType.BALANCE_SHEET),
        (PEER_1, income_period, FinancialStatementType.INCOME_STATEMENT),
        (PEER_2, balance_period, FinancialStatementType.BALANCE_SHEET),
        (PEER_2, income_period, FinancialStatementType.INCOME_STATEMENT),
    }
    assert all(job[0] != PRIMARY for job in client.executed_jobs)
    assert any("0/2 entidades" in message for message in diagnostics)


def test_methodology_history_requires_twelve_balances_and_three_result_periods() -> None:
    lines: list[FinancialStatementLine] = []
    start = date(2025, 8, 1)
    for offset in range(12):
        month = SUGEFOfficialFinancialApiClient._shift_month(start, offset)
        month_end = date(month.year, month.month, monthrange(month.year, month.month)[1])
        lines.append(
            _line(
                PEER_1,
                month_end,
                FinancialStatementType.BALANCE_SHEET,
                account_name="ACTIVO TOTAL",
            )
        )
    for result_date in (
        date(2025, 7, 31),
        date(2025, 12, 31),
        CUTOFF,
    ):
        lines.append(
            _line(
                PEER_1,
                result_date,
                FinancialStatementType.INCOME_STATEMENT,
                account_name="RESULTADO FINAL",
            )
        )

    assert SUGEFOfficialFinancialApiClient._has_methodology_history(
        lines,
        PEER_1,
        CUTOFF,
    )
