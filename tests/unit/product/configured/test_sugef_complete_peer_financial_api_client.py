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
from aip.product.configured.readers.sugef_complete_peer_financial_api_client import (
    SUGEFCompletePeerFinancialApiClient,
)


class _RecoveringClient(SUGEFCompletePeerFinancialApiClient):
    def __init__(self) -> None:
        super().__init__(SUGEFFinancialSourceConfig(api_entity_codes=("PRIMARY",)))
        self.executed_jobs: list[
            tuple[str, str, str, str, FinancialStatementType, str]
        ] = []

    def _execute_filtered_jobs(
        self,
        jobs: list[tuple[str, str, str, str, FinancialStatementType, str]],
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        self.executed_jobs.extend(jobs)
        entity_codes = sorted({job[0] for job in jobs})
        cutoff = date(2026, 7, 31)
        for entity_code in entity_codes:
            entity = FinancialEntity(entity_code, f"Entidad {entity_code}")
            for account_code in self._METHODOLOGY_BALANCE_ACCOUNTS:
                for offset in range(self._AVERAGE_LOOKBACK_MONTHS + 1):
                    month = cutoff.month - offset
                    year = cutoff.year
                    while month <= 0:
                        month += 12
                        year -= 1
                    statement_date = self._month_end_date(year, month)
                    lines.append(
                        FinancialStatementLine(
                            entity=entity,
                            statement_date=statement_date,
                            statement_type=FinancialStatementType.BALANCE_SHEET,
                            account_code=account_code,
                            account_name=account_code,
                            amount=Decimal("1"),
                        )
                    )
            required_income_dates = (
                cutoff,
                self._month_end_date(cutoff.year - 1, cutoff.month),
                self._month_end_date(cutoff.year - 1, 12),
            )
            for account_code in self._METHODOLOGY_INCOME_ACCOUNTS:
                for statement_date in required_income_dates:
                    lines.append(
                        FinancialStatementLine(
                            entity=entity,
                            statement_date=statement_date,
                            statement_type=FinancialStatementType.INCOME_STATEMENT,
                            account_code=account_code,
                            account_name=account_code,
                            amount=Decimal("1"),
                        )
                    )
        endpoints.add("test://filtered")


def _indicator_line(entity_code: str) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=FinancialEntity(entity_code, f"Entidad {entity_code}"),
        statement_date=date(2026, 7, 31),
        statement_type=FinancialStatementType.INDICATORS,
        account_code="IND",
        account_name="ROA",
        amount=Decimal("0.01"),
    )


def test_recovery_is_not_limited_to_four_incomplete_peers() -> None:
    client = _RecoveringClient()
    peer_codes = tuple(f"PEER-{index}" for index in range(1, 7))
    lines = [_indicator_line(code) for code in peer_codes]
    endpoints: set[str] = set()
    diagnostics: list[str] = []

    client._recover_incomplete_peer_history(
        date(2026, 7, 31),
        lines,
        endpoints,
        diagnostics,
    )

    recovered_entities = {job[0] for job in client.executed_jobs}
    assert recovered_entities == set(peer_codes)
    assert len(recovered_entities) == 6
    assert all(
        client._has_methodology_history(lines, code, date(2026, 7, 31))
        for code in peer_codes
    )
    assert any("6/6 entidades" in message for message in diagnostics)


def test_recovery_queries_only_accounts_with_missing_history() -> None:
    client = _RecoveringClient()
    cutoff = date(2026, 7, 31)
    entity = FinancialEntity("PEER-1", "Entidad PEER-1")
    lines: list[FinancialStatementLine] = [_indicator_line(entity.entity_id)]

    # Account 10000 already has complete 12-month balance history.
    for offset in range(client._AVERAGE_LOOKBACK_MONTHS + 1):
        month = cutoff.month - offset
        year = cutoff.year
        while month <= 0:
            month += 12
            year -= 1
        lines.append(
            FinancialStatementLine(
                entity=entity,
                statement_date=client._month_end_date(year, month),
                statement_type=FinancialStatementType.BALANCE_SHEET,
                account_code="10000",
                account_name="10000",
                amount=Decimal("1"),
            )
        )

    jobs = client._missing_methodology_history_jobs(
        entity_codes=(entity.entity_id,),
        lines=lines,
        cutoff_date=cutoff,
    )

    requested_accounts = {job[-1] for job in jobs}
    assert "10000" not in requested_accounts
    assert "25000" in requested_accounts
    assert set(client._METHODOLOGY_INCOME_ACCOUNTS).issubset(requested_accounts)
