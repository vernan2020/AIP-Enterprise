from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiResponse
from aip.product.configured.readers.sugef_resilient_credit_quality_reader import (
    SUGEFResilientCreditQualityReader,
)

_PRIMARY = "3004045138"
_BCT = "3004009999"


def _row(
    entity: str,
    band: str,
    amount: str | None,
    *,
    normative: str = "1",
) -> dict[str, object]:
    return {
        "codigoEntidad": entity,
        "aliasPublicacionEntidad": "BANCO BCT" if entity == _BCT else "COOPEALIANZA R.L.",
        "nombreTipoEntidad": "BANCOS PRIVADOS Y COOPERATIVOS",
        "periodo": "2026-07-01T00:00:00",
        "normativa": normative,
        "maximoAtraso": band,
        "saldoPrincipal": amount,
    }


class _TargetedBandApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def read_credit_report(
        self,
        report_name: str,
        *,
        entity_code: str = "",
        sector_code: str = "",
        periods: str,
        regulation: str = "1",
        days_arrears: str | None = None,
        historical: bool = False,
    ) -> SUGEFPublicApiResponse:
        del report_name, sector_code, periods, historical
        day = "" if days_arrears is None else days_arrears
        self.calls.append((entity_code, regulation, day))

        primary_rows = [
            _row(_PRIMARY, "1", "950"),
            _row(_PRIMARY, "2", "15"),
            _row(_PRIMARY, "3", "10"),
            _row(_PRIMARY, "4", "5"),
            _row(_PRIMARY, "5", "10"),
            _row(_PRIMARY, "6", "10"),
            _row(_PRIMARY, "7", "0"),
        ]
        bct_general = [
            _row(_BCT, "1", None),
            _row(_BCT, "2", "10"),
            _row(_BCT, "3", "10"),
            _row(_BCT, "4", "10"),
            _row(_BCT, "5", "10"),
            _row(_BCT, "6", "10"),
            _row(_BCT, "7", "10"),
        ]

        if entity_code == _PRIMARY:
            rows = primary_rows
        elif entity_code == "":
            rows = [*primary_rows, *bct_general]
        elif entity_code == _BCT and day == "1":
            rows = [_row(_BCT, "1", "940")]
        elif entity_code == _BCT:
            rows = bct_general
        else:
            rows = []

        return SUGEFPublicApiResponse(
            operation="/ReporteCrediticio/MAPI/ReporteDiasAtraso",
            endpoint="https://sugef.example/ReporteDiasAtraso",
            method="POST",
            body={"listaReporteDiasAtraso": rows},
            rows=tuple(rows),
        )


def test_targeted_day_query_recovers_valid_current_portfolio_after_null_bulk_row() -> None:
    api = _TargetedBandApi()
    reader = SUGEFResilientCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=(_PRIMARY,)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(
        date(2026, 7, 31),
        expected_entity_codes=(_PRIMARY, _BCT),
    )

    bct = {
        line.account_code: line.amount
        for line in result.lines
        if line.entity.entity_id == _BCT
        and line.statement_type is FinancialStatementType.INDICATORS
    }
    assert bct["CALC:CURRENT_PORTFOLIO"] == Decimal("0.94")
    assert bct["CALC:DELINQUENCY_90"] == Decimal("0.03")
    assert (_BCT, "1", "1") in api.calls
    assert any(
        "BANCO BCT" in message
        and "CURRENT" in message
        and "consulta oficial dirigida" in message
        for message in result.diagnostics
    )


class _TargetedNullApi(_TargetedBandApi):
    def read_credit_report(self, *args, **kwargs) -> SUGEFPublicApiResponse:  # type: ignore[no-untyped-def]
        response = super().read_credit_report(*args, **kwargs)
        entity_code = str(kwargs.get("entity_code", ""))
        day = str(kwargs.get("days_arrears", ""))
        if entity_code == _BCT and day == "1":
            rows = [_row(_BCT, "1", None)]
            return SUGEFPublicApiResponse(
                operation=response.operation,
                endpoint=response.endpoint,
                method=response.method,
                body={"listaReporteDiasAtraso": rows},
                rows=tuple(rows),
            )
        return response


def test_targeted_explicit_null_remains_unavailable_and_is_not_zero() -> None:
    reader = SUGEFResilientCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=(_PRIMARY,)),
        api_client=_TargetedNullApi(),  # type: ignore[arg-type]
    )

    result = reader.read(
        date(2026, 7, 31),
        expected_entity_codes=(_PRIMARY, _BCT),
    )

    assert all(line.entity.entity_id != _BCT for line in result.lines)
    assert any(
        "BANCO BCT" in message
        and "saldo principal es nulo o inválido" in message
        and "se conserva N/D" in message
        for message in result.diagnostics
    )
