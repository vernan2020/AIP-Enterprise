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
    def __init__(
        self,
        *,
        missing_band: str | None = None,
        second_complete_normative: bool = False,
        second_missing_band: str | None = None,
        duplicate_current_row: bool = False,
    ) -> None:
        self.missing_band = missing_band
        self.second_complete_normative = second_complete_normative
        self.second_missing_band = second_missing_band
        self.duplicate_current_row = duplicate_current_row
        self.calls: list[tuple[str, str, str]] = []

    @staticmethod
    def _rows(normative: str, *, missing_band: str | None = None) -> list[dict[str, str]]:
        balances = {
            "1": "900",
            "2": "20",
            "3": "20",
            "4": "10",
            "5": "20",
            "6": "20",
            "7": "10",
        }
        return [
            {
                "codigoEntidad": "3004045138",
                "aliasPublicacionEntidad": "COOPEALIANZA R.L.",
                "nombreTipoEntidad": "Cooperativas",
                "periodo": "2026-07-01T00:00:00",
                "normativa": normative,
                "maximoAtraso": band,
                "saldoPrincipal": amount,
            }
            for band, amount in balances.items()
            if band != missing_band
        ]

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
        self.calls.append((entity_code, periods, regulation))
        rows: list[dict[str, str]] = []
        if entity_code == "3004045138":
            rows.extend(self._rows("1", missing_band=self.missing_band))
            if self.duplicate_current_row:
                rows.append(
                    {
                        "codigoEntidad": "3004045138",
                        "aliasPublicacionEntidad": "COOPEALIANZA R.L.",
                        "nombreTipoEntidad": "Cooperativas",
                        "periodo": "2026-07-01T00:00:00",
                        "normativa": "1",
                        "maximoAtraso": "1",
                        "saldoPrincipal": "100",
                    }
                )
            if self.second_complete_normative:
                rows.extend(self._rows("2", missing_band=self.second_missing_band))
        elif entity_code == "":
            # El scope SFN incluye de nuevo a Coopealianza. Este registro no debe
            # sumarse porque la entidad ya fue consultada directamente.
            rows.append(
                {
                    "codigoEntidad": "3004045138",
                    "aliasPublicacionEntidad": "COOPEALIANZA R.L.",
                    "nombreTipoEntidad": "Cooperativas",
                    "periodo": "2026-07-01T00:00:00",
                    "normativa": "1",
                    "maximoAtraso": "1",
                    "saldoPrincipal": "9000",
                }
            )
        return SUGEFPublicApiResponse(
            operation="/ReporteCrediticio/MAPI/ReporteDiasAtraso",
            endpoint="https://sugef.example/ReporteDiasAtraso",
            method="POST",
            body={"listaReporteDiasAtraso": rows},
            rows=tuple(rows),
        )


def _indicators(result: object) -> dict[str, Decimal]:
    lines = result.lines  # type: ignore[attr-defined]
    return {
        line.account_code: line.amount
        for line in lines
        if line.statement_type is FinancialStatementType.INDICATORS
    }


def test_reader_calculates_current_and_over_90_indicators_from_all_sugef_bands() -> None:
    api = _StubPublicApiClient()
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    assert _indicators(result) == {
        "CALC:CURRENT_PORTFOLIO": Decimal("0.9"),
        "CALC:DELINQUENCY_90": Decimal("0.05"),
    }
    assert ("3004045138", "20260701", "") in api.calls
    assert ("", "20260701", "") in api.calls
    assert any("todas las normativas aplicables" in item for item in result.diagnostics)
    assert any("sin completar bandas ausentes con cero" in item for item in result.diagnostics)


def test_reader_preserves_legitimate_multiple_rows_within_same_normative() -> None:
    api = _StubPublicApiClient(duplicate_current_row=True)
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))
    indicators = _indicators(result)

    assert indicators["CALC:CURRENT_PORTFOLIO"] == Decimal("1000") / Decimal("1100")
    assert indicators["CALC:DELINQUENCY_90"] == Decimal("50") / Decimal("1100")


def test_reader_leaves_credit_quality_unavailable_when_one_band_is_missing() -> None:
    api = _StubPublicApiClient(missing_band="7")
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    assert result.lines == ()
    assert any("JUDICIAL_COLLECTION" in item for item in result.diagnostics)


def test_reader_aggregates_multiple_complete_normatives_for_total_entity_portfolio() -> None:
    api = _StubPublicApiClient(second_complete_normative=True)
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    assert _indicators(result) == {
        "CALC:CURRENT_PORTFOLIO": Decimal("0.9"),
        "CALC:DELINQUENCY_90": Decimal("0.05"),
    }
    assert any("normativas SUGEF completas (1, 2)" in item for item in result.diagnostics)
    assert all(line.trace is not None for line in result.lines)
    assert all("normativas 1, 2" in line.trace.file_path for line in result.lines if line.trace)


def test_reader_does_not_drop_an_incomplete_reported_normative() -> None:
    api = _StubPublicApiClient(second_complete_normative=True, second_missing_band="7")
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    assert result.lines == ()
    assert any("normativa 2" in item for item in result.diagnostics)
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
