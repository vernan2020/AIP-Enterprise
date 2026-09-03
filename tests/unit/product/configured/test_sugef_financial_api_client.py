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
        assert payload["parametrosEntidad"] == {
            "codigoEntidad": "3004045138",
            "periodos": "20260731",
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
                        "periodo": "2026-07-01T00:00:00",
                        "cuentaIASEF": "1000000000000",
                        "nombreCuenta": "TOTAL ACTIVO",
                        "saldoIASEF": 819887005703.77,
                    }
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
                }
            ],
        }


def test_api_client_maps_reports_and_normalizes_reporting_month_end() -> None:
    client = _StubClient(
        SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=("3004045138",))
    )

    result = client.read(date(2026, 7, 31))

    assert len(result.lines) == 2
    assert {line.statement_type for line in result.lines} == {
        FinancialStatementType.BALANCE_SHEET,
        FinancialStatementType.INDICATORS,
    }
    assert all(line.statement_date == date(2026, 7, 31) for line in result.lines)
    assert result.lines[0].entity.entity_id == "3004045138"
    assert any(line.amount == Decimal("819887005703.77") for line in result.lines)
    assert all(line.amount != Decimal("0") for line in result.lines)
    assert all(line.trace is not None for line in result.lines)
