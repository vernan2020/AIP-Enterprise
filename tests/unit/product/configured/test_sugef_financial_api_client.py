from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_financial_api_client import (
    SUGEFFinancialApiClient,
)


class _StubClient(SUGEFFinancialApiClient):
    def _post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        expected_period = (
            "20250801-20260701"
            if "BalanceSituacion" in endpoint
            else (
                "20250501,20250601,20250701,20251201,20260501,20260601,20260701"
                if "EstadoResultados" in endpoint
                else "20260501-20260701"
            )
        )
        assert payload["parametrosEntidad"] == {
            "codigoEntidad": "3004045138",
            "periodos": expected_period,
            "codigoCuenta": "",
        }
        if "BalanceSituacion" in endpoint:
            return {
                "tieneError": False,
                "listaBalanceSituacionAnalisisFinancieroEntidad": [
                    {
                        "codigoSector": "6",
                        "descripcionSector": "Cooperativas",
                        "codigoEntidad": "3004045138",
                        "nombreEntidad": "COOPEALIANZA R.L.",
                        "periodo": f"{period}T00:00:00",
                        "cuentaIASEF": "1000000000000",
                        "nombreCuenta": "TOTAL ACTIVO",
                        "saldoIASEF": 819887005703.77,
                    }
                    for period in (
                        "2025-08-01",
                        "2025-09-01",
                        "2025-10-01",
                        "2025-11-01",
                        "2025-12-01",
                        "2026-01-01",
                        "2026-02-01",
                        "2026-03-01",
                        "2026-04-01",
                        "2026-05-01",
                        "2026-06-01",
                        "2026-07-01",
                    )
                ],
            }
        if "EstadoResultados" in endpoint:
            return {
                "tieneError": False,
                "listaEstadoResultadosAnalisisFinancieroEntidad": [
                    {
                        "codigoSector": "6",
                        "descripcionSector": "Cooperativas",
                        "codigoEntidad": "3004045138",
                        "nombreEntidad": "COOPEALIANZA R.L.",
                        "periodo": "2026-07-01T00:00:00",
                        "cuentaIASEF": "5000000000000",
                        "nombreCuenta": "RESULTADO DEL PERIODO",
                        "saldoIASEF": None,
                    }
                ],
            }
        return {
            "tieneError": False,
            "listaIndicadoresFinancierosEntidad": [
                {
                    "codigoSector": "6",
                    "descripcionSector": "Cooperativas",
                    "codigoEntidad": "3004045138",
                    "nombreEntidad": "COOPEALIANZA R.L.",
                    "periodo": "2026-07-01T00:00:00",
                    "codigoIndicador": "ROA",
                    "nombreIndicador": "ROA",
                    "valorIndicador": 1.04,
                },
                {
                    "codigoSector": "6",
                    "descripcionSector": "Cooperativas",
                    "codigoEntidad": "3004045138",
                    "nombreEntidad": "COOPEALIANZA R.L.",
                    "periodo": "2026-07-01T00:00:00",
                    "codigoIndicador": 12011.0,
                    "nombreIndicador": "Cobertura de cartera",
                    "valorIndicador": 5.0,
                    "numerador": 500.0,
                    "denominador": 100.0,
                },
            ],
        }


def test_api_client_maps_reports_and_normalizes_reporting_month_end() -> None:
    client = _StubClient(
        SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=("3004045138",))
    )

    result = client.read(date(2026, 7, 31))

    assert len(result.lines) == 14
    assert {line.statement_type for line in result.lines} == {
        FinancialStatementType.BALANCE_SHEET,
        FinancialStatementType.INDICATORS,
    }
    assert max(line.statement_date for line in result.lines) == date(2026, 7, 31)
    assert min(line.statement_date for line in result.lines) == date(2025, 8, 31)
    assert result.lines[0].entity.entity_id == "3004045138"
    assert any(line.amount == Decimal("819887005703.77") for line in result.lines)
    assert any(line.amount == Decimal("0.0104") for line in result.lines)
    assert any(
        line.account_code == "12011" and line.amount == Decimal("5") for line in result.lines
    )
    assert all(line.amount != Decimal("0") for line in result.lines)
    assert all(line.trace is not None for line in result.lines)
    assert any("31/07/2026" in item for item in result.diagnostics)


def test_api_client_uses_first_of_month_range_across_year_boundary() -> None:
    assert SUGEFFinancialApiClient._period_range(date(2026, 1, 31)) == ("20251101-20260101")
    assert SUGEFFinancialApiClient._period_range(date(2026, 1, 31), lookback_months=11) == (
        "20250201-20260101"
    )


def test_api_client_generates_prior_ranges_for_sugef_publication_lag() -> None:
    assert SUGEFFinancialApiClient._fallback_periods("20250901-20260801") == (
        "20250901-20260801",
        "20250801-20260701",
        "20250701-20260601",
    )


def test_api_client_requests_only_ttm_result_periods() -> None:
    assert SUGEFFinancialApiClient._result_periods(date(2026, 7, 31)) == (
        "20250501,20250601,20250701,20251201,20260501,20260601,20260701"
    )
