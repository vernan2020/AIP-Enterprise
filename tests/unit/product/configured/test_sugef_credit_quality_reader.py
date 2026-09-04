from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_credit_quality_reader import (
    SUGEFCreditQualityReader,
)
from aip.product.configured.readers.sugef_public_api_client import (
    SUGEFPublicApiResponse,
)


class _StubPublicApiClient:
    def __init__(self, *, missing_band: str | None = None) -> None:
        self.missing_band = missing_band
        self.calls: list[tuple[str, str]] = []

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
        self.calls.append((entity_code, periods))
        rows = []
        if entity_code == "3004045138":
            balances = {
                "1": "900",
                "2": "20",
                "3": "20",
                "4": "10",
                "5": "20",
                "6": "20",
                "7": "10",
            }
            rows = [
                {
                    "codigoEntidad": "3004045138",
                    "aliasPublicacionEntidad": "COOPEALIANZA R.L.",
                    "nombreTipoEntidad": "Cooperativas",
                    "periodo": "2026-07-01T00:00:00",
                    "maximoAtraso": band,
                    "saldoPrincipal": amount,
                }
                for band, amount in balances.items()
                if band != self.missing_band
            ]
        return SUGEFPublicApiResponse(
            operation="/ReporteCrediticio/MAPI/ReporteDiasAtraso",
            endpoint="https://sugef.example/ReporteDiasAtraso",
            method="POST",
            body={"listaReporteDiasAtraso": rows},
            rows=tuple(rows),
        )


def test_reader_calculates_current_and_over_90_indicators_from_all_sugef_bands() -> None:
    api = _StubPublicApiClient()
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    indicators = {
        line.account_code: line.amount
        for line in result.lines
        if line.statement_type is FinancialStatementType.INDICATORS
    }
    assert indicators == {
        "CALC:CURRENT_PORTFOLIO": Decimal("0.9"),
        "CALC:DELINQUENCY_90": Decimal("0.05"),
    }
    assert ("3004045138", "20260701") in api.calls
    assert ("", "20260701") in api.calls
    assert any("sin completar bandas ausentes con cero" in item for item in result.diagnostics)


def test_reader_leaves_credit_quality_unavailable_when_one_band_is_missing() -> None:
    api = _StubPublicApiClient(missing_band="7")
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    assert result.lines == ()
    assert any("JUDICIAL_COLLECTION" in item for item in result.diagnostics)


def test_reader_does_not_apply_current_credit_family_before_2024() -> None:
    api = _StubPublicApiClient()
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2023, 12, 31))

    assert result.lines == ()
    assert api.calls == []
    assert any("Hasta2023" in item for item in result.diagnostics)
