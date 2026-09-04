from __future__ import annotations

from typing import Any

import pytest

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiClient


class _StubSUGEFPublicApiClient(SUGEFPublicApiClient):
    def __init__(self) -> None:
        super().__init__(SUGEFFinancialSourceConfig(api_retries=0))
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def _request_json(
        self,
        endpoint: str,
        *,
        method: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.calls.append((endpoint, method, payload))
        if "ListarEntidades" in endpoint:
            return {
                "listaEntidades": [
                    {
                        "codigoEntidad": "3004045138",
                        "nombreEntidad": "COOPEALIANZA R.L.",
                        "descripcionSector": "COOPERATIVAS",
                    }
                ]
            }
        if "ReporteDiasAtraso" in endpoint:
            return {
                "tieneError": False,
                "listaDiasAtraso": [
                    {
                        "codigoEntidad": "3004045138",
                        "maximoAtraso": "91-120",
                        "saldoPrincipal": None,
                    }
                ],
            }
        return {"tieneError": False, "listaPrueba": []}


def test_catalog_entity_operation_is_get_and_extracts_rows() -> None:
    client = _StubSUGEFPublicApiClient()

    result = client.list_entities()

    assert result.method == "GET"
    assert result.rows[0]["codigoEntidad"] == "3004045138"
    endpoint, method, payload = client.calls[-1]
    assert "/Catalogo/MAPI/ListarEntidades?" in endpoint
    assert method == "GET"
    assert payload is None


def test_encaje_builds_official_parameter_wrapper() -> None:
    client = _StubSUGEFPublicApiClient()

    client.read_encaje_legal(
        entity_code="3004045138",
        sector_code="6",
        periods="20260701",
        currency="Colón",
    )

    _, method, payload = client.calls[-1]
    assert method == "POST"
    assert payload == {
        "parametrosEncajeLegal": {
            "codigoEntidad": "3004045138",
            "codigoTipoEntidad": "6",
            "periodos": "20260701",
            "tipoMoneda": "Colón",
        }
    }


def test_credit_days_arrears_uses_documented_wrapper_and_preserves_null() -> None:
    client = _StubSUGEFPublicApiClient()

    result = client.read_credit_report(
        "ReporteDiasAtraso",
        entity_code="3004045138",
        sector_code="6",
        periods="20260701",
        regulation="1",
        days_arrears="91-120",
    )

    _, method, payload = client.calls[-1]
    assert method == "POST"
    assert payload == {
        "parametrosCrediticioDiasAtraso": {
            "codigoEntidad": "3004045138",
            "codigoTipoEntidad": "6",
            "periodos": "20260701",
            "normativa": "1",
            "diasAtraso": "91-120",
        }
    }
    assert result.rows[0]["saldoPrincipal"] is None


def test_historical_credit_report_is_scoped_to_historical_family() -> None:
    client = _StubSUGEFPublicApiClient()

    client.read_credit_report(
        "ReporteCategoriaRiesgoHasta2023",
        entity_code="3004045138",
        periods="20231201",
        regulation="1",
        historical=True,
    )

    endpoint, _, _ = client.calls[-1]
    assert "/ReporteCrediticioHasta2023/MAPI/ReporteCategoriaRiesgoHasta2023?" in endpoint


def test_financial_reports_support_entity_sector_and_total_wrappers() -> None:
    client = _StubSUGEFPublicApiClient()

    client.read_financial_entity_report(
        "ReporteBalanzaComprobacionEntidad",
        entity_code="3004045138",
        periods="20260701",
        account_code="10000",
    )
    _, _, entity_payload = client.calls[-1]
    assert entity_payload == {
        "parametrosEntidad": {
            "codigoEntidad": "3004045138",
            "periodos": "20260701",
            "codigoCuenta": "10000",
        }
    }

    client.read_financial_sector_report(
        "ReporteIndicadoresFinancierosSector",
        sector_code="6",
        periods="20260701",
    )
    _, _, sector_payload = client.calls[-1]
    assert sector_payload == {
        "parametrosSector": {
            "codigoTipoEntidad": "6",
            "periodos": "20260701",
            "codigoCuenta": "",
        }
    }

    client.read_financial_total_report(
        "ReporteIndicadoresFinancierosTotal",
        periods="20260701",
    )
    _, _, total_payload = client.calls[-1]
    assert total_payload == {
        "parametrosTotal": {"periodos": "20260701", "codigoCuenta": ""}
    }


def test_gateway_rejects_external_or_unknown_operation_families() -> None:
    client = _StubSUGEFPublicApiClient()

    with pytest.raises(ValueError):
        client.request("https://example.com/data", method="GET")
    with pytest.raises(ValueError):
        client.request("/OtraAPI/MAPI/Reporte", method="GET")
