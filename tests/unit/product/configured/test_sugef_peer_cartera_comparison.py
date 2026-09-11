from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import FinancialStatementLine, FinancialStatementType
from aip.domain.financial_analysis.services import FinancialAnalysisService
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_official_financial_api_client import (
    SUGEFOfficialFinancialApiClient,
    _PrimaryProbe,
)

_PRIMARY = "4000000019"
_PEERS = (
    (_PRIMARY, "BANCO PRINCIPAL"),
    ("4000000020", "BANCO PAR 1"),
    ("4000000021", "BANCO PAR 2"),
)
_CUTOFF = date(2026, 7, 31)
_DYNAMIC_LOAN_ACCOUNT = "77777"


class _DynamicLoanAccountClient(SUGEFOfficialFinancialApiClient):
    """Stub proving that peer cartera is discovered, never hardcoded."""

    def __init__(self) -> None:
        super().__init__(SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=(_PRIMARY,)))
        self.filtered_jobs: list[tuple[str, str, str, str, FinancialStatementType, str]] = []

    def _statement_line(
        self,
        *,
        entity_code: str,
        entity_name: str,
        statement_type: FinancialStatementType,
        account_code: str,
        account_name: str,
        amount: Decimal,
    ) -> FinancialStatementLine:
        if statement_type is FinancialStatementType.INDICATORS:
            row = {
                "codigoSector": "1",
                "descripcionSector": "BANCOS COMERCIALES DEL ESTADO",
                "codigoEntidad": entity_code,
                "nombreEntidad": entity_name,
                "periodo": "2026-07-01T00:00:00",
                "codigoIndicador": account_code,
                "nombreIndicador": account_name,
                "valorIndicador": float(amount),
            }
            list_key = self._INDICATOR_REPORT[1]
        else:
            row = {
                "codigoSector": "1",
                "descripcionSector": "BANCOS COMERCIALES DEL ESTADO",
                "codigoEntidad": entity_code,
                "nombreEntidad": entity_name,
                "periodo": "2026-07-01T00:00:00",
                "cuentaIASEF": account_code,
                "nombreCuenta": account_name,
                "saldoIASEF": float(amount),
            }
            list_key = (
                self._BALANCE_REPORT[1]
                if statement_type is FinancialStatementType.BALANCE_SHEET
                else self._INCOME_REPORT[1]
            )
        line = self._line(
            row,
            statement_type,
            "https://sugef.example/report",
            list_key,
            1,
        )
        assert line is not None
        return line

    def _resolve_primary_statement_cutoff(
        self,
        requested_cutoff: date,
        diagnostics: list[str],
    ) -> _PrimaryProbe | None:
        del requested_cutoff, diagnostics
        primary_name = _PEERS[0][1]
        balance = (
            self._statement_line(
                entity_code=_PRIMARY,
                entity_name=primary_name,
                statement_type=FinancialStatementType.BALANCE_SHEET,
                account_code="10000",
                account_name="ACTIVO TOTAL",
                amount=Decimal("8700000000000"),
            ),
            self._statement_line(
                entity_code=_PRIMARY,
                entity_name=primary_name,
                statement_type=FinancialStatementType.BALANCE_SHEET,
                account_code=_DYNAMIC_LOAN_ACCOUNT,
                account_name="CARTERA DE CRÉDITO",
                amount=Decimal("5260000000000"),
            ),
            self._statement_line(
                entity_code=_PRIMARY,
                entity_name=primary_name,
                statement_type=FinancialStatementType.BALANCE_SHEET,
                account_code="25000",
                account_name="PATRIMONIO TOTAL",
                amount=Decimal("960000000000"),
            ),
        )
        income = (
            self._statement_line(
                entity_code=_PRIMARY,
                entity_name=primary_name,
                statement_type=FinancialStatementType.INCOME_STATEMENT,
                account_code="30000",
                account_name="RESULTADO FINAL",
                amount=Decimal("35000000000"),
            ),
        )
        return _PrimaryProbe(
            cutoff=_CUTOFF,
            balance_lines=balance,
            income_lines=income,
            endpoints=("balance", "income"),
        )

    def _execute_jobs(
        self,
        jobs: list[tuple[str, str, str, str, FinancialStatementType]],
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        del endpoints, diagnostics
        for entity_code, _period, _report_name, _list_key, statement_type in jobs:
            if statement_type is not FinancialStatementType.INDICATORS:
                continue
            entities = _PEERS if entity_code == "" else (_PEERS[0],)
            for code, name in entities:
                lines.append(
                    self._statement_line(
                        entity_code=code,
                        entity_name=name,
                        statement_type=FinancialStatementType.INDICATORS,
                        account_code="ROA",
                        account_name="ROA",
                        amount=Decimal("1.10"),
                    )
                )

    def _execute_filtered_jobs(
        self,
        jobs: list[tuple[str, str, str, str, FinancialStatementType, str]],
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        del endpoints, diagnostics
        self.filtered_jobs.extend(jobs)
        for entity_code, _period, _report_name, _list_key, statement_type, account_code in jobs:
            if (
                entity_code != ""
                or statement_type is not FinancialStatementType.BALANCE_SHEET
                or account_code != _DYNAMIC_LOAN_ACCOUNT
            ):
                continue
            for index, (code, name) in enumerate(_PEERS):
                lines.append(
                    self._statement_line(
                        entity_code=code,
                        entity_name=name,
                        statement_type=FinancialStatementType.BALANCE_SHEET,
                        account_code=_DYNAMIC_LOAN_ACCOUNT,
                        account_name="CARTERA DE CRÉDITO",
                        amount=Decimal("5260000000000") - Decimal(index * 100000000000),
                    )
                )


def test_peer_comparison_recovers_cartera_using_dynamic_primary_account() -> None:
    client = _DynamicLoanAccountClient()

    result = client.read(_CUTOFF)

    assert any(
        entity_code == ""
        and statement_type is FinancialStatementType.BALANCE_SHEET
        and account_code == _DYNAMIC_LOAN_ACCOUNT
        for entity_code, _period, _report, _list_key, statement_type, account_code in client.filtered_jobs
    )
    assert any(
        "Cartera comparativa SFN" in message and _DYNAMIC_LOAN_ACCOUNT in message
        for message in result.diagnostics
    )

    snapshot = FinancialAnalysisService().build_snapshot(
        result.lines,
        selected_entity_id=_PRIMARY,
        cutoff_date=_CUTOFF,
    )
    loans_by_entity = {
        summary.entity.entity_id: summary.loans for summary in snapshot.peer_summaries
    }

    assert loans_by_entity[_PRIMARY] == Decimal("5260000000000.0")
    assert loans_by_entity["4000000020"] == Decimal("5160000000000.0")
    assert loans_by_entity["4000000021"] == Decimal("5060000000000.0")
    assert all(value is not None for value in loans_by_entity.values())
