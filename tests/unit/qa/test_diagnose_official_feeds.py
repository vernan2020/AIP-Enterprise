"""Official source smoke diagnostics must never disclose credentials."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from urllib.error import HTTPError

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from scripts.qa import diagnose_official_feeds as check


def test_report_counts_are_read_only_and_schema_tolerant() -> None:
    assert (
        check._records(
            {"listaBalanzaComprobacionEntidad": [{"a": 1}]}, "listaBalanzaComprobacionEntidad"
        )
        == 1
    )
    assert (
        check._records(
            {"LISTABALANZACOMPROBACIONENTIDAD": [{"a": 1}]}, "listaBalanzaComprobacionEntidad"
        )
        == 1
    )
    assert (
        check._records(
            {"tieneError": True, "listaBalanzaComprobacionEntidad": [{}]},
            "listaBalanzaComprobacionEntidad",
        )
        == 0
    )


def test_sugef_period_and_credentials_never_appear(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        def __init__(self, config) -> None:
            self.config = config

        def _endpoint(self, name: str) -> str:
            return name

        def _post_json(self, endpoint: str, payload: dict) -> dict:
            calls.append((endpoint, payload))
            return {
                {
                    "ReporteBalanzaComprobacionEntidad": "listaBalanzaComprobacionEntidad",
                    "ReporteBalanceSituacionContableDespuesMarzo2020Entidad": "listaBalanceSituacionContableEntidad",
                    "ReporteEstadoResultadosContableDespuesMarzo2020Entidad": "listaEstadoResultadosContableEntidad",
                }[endpoint]: [{"periodo": "2026-09-01"}]
            }

    monkeypatch.setattr(check, "SUGEFFinancialApiClient", FakeClient)
    config = SUGEFFinancialSourceConfig(
        enabled=True,
        api_enabled=True,
        api_entity_codes=("3004045138",),
        api_timeout_seconds=90,
        api_retries=2,
    )
    messages = check._sugef_probe(config, target_date=date(2026, 9, 1))
    assert all("1 registros" in x for x in messages)
    assert len(calls) == 3
    assert all(payload["parametrosEntidad"]["periodos"] == "20260901" for _, payload in calls)
    assert "3004045138" not in " ".join(messages)


def test_safe_network_errors_do_not_reveal_request_urls() -> None:
    url = "https://private.invalid?password=TOPSECRET"
    err = HTTPError(url, 403, "access denied", hdrs=None, fp=None)
    assert check._outcome(err) == "HTTP 403"
    assert url not in check._outcome(err)


def test_probe_respects_missing_existing_tokens() -> None:
    status = check._bccr_probe(SimpleNamespace(token=None), target_date=date(2026, 10, 13))
    assert "CREDENCIAL NO VISIBLE" in status


def test_sugef_probe_does_not_treat_old_report_as_september() -> None:
    response = {"listaBalanceSituacionContableEntidad": [{"periodo": "2026-08-01T00:00:00"}]}
    message = check._period_coverage(
        response,
        "listaBalanceSituacionContableEntidad",
        target_date=date(2026, 9, 1),
    )
    assert "2026-09 AUSENTE" in message
    assert "2026-08" in message
    assert (
        check._period_coverage(
            {"listaBalanceSituacionContableEntidad": [{"periodo": "2026-09-01T00:00:00"}]},
            "listaBalanceSituacionContableEntidad",
            target_date=date(2026, 9, 1),
        )
        == "CORTE 2026-09 PRESENTE"
    )


def test_sugef_probe_does_not_claim_valid_report_when_schema_is_missing() -> None:
    assert (
        check._period_coverage(
            {"tieneError": False, "otraClave": []},
            "listaBalanceSituacionContableEntidad",
            target_date=date(2026, 9, 1),
        )
        == "ESQUEMA INESPERADO"
    )


def test_bccr_diagnostic_rejects_error_envelopes_and_reports_actual_dates() -> None:
    assert check._bccr_fx_coverage({"estado": False, "mensaje": "error"}) == (
        "RESPUESTA OFICIAL NO EXITOSA"
    )
    assert check._bccr_fx_coverage({"estado": True, "datos": {}}) == "ESQUEMA INESPERADO"
    observed = check._bccr_fx_coverage(
        {
            "estado": True,
            "datos": [
                {
                    "indicadores": [
                        {
                            "codigoIndicador": 317,
                            "series": [
                                {"fecha": "2026-10-10T00:00:00", "valorDatoPorPeriodo": 100.00},
                                {"fecha": "2026-10-14T00:00:00", "valorDatoPorPeriodo": 101.00},
                            ],
                        },
                        {
                            "codigoIndicador": 318,
                            "series": [{"fecha": "2026-10-14", "valorDatoPorPeriodo": 102.00}],
                        },
                    ]
                }
            ],
        }
    )
    assert "compra: 2 obs; último 2026-10-14" in observed
    assert "venta: 1 obs; último 2026-10-14" in observed
    assert "101.0" not in observed
    assert "102.0" not in observed


def test_bccr_probe_can_distinguish_chart_500_from_live_individual_fx(monkeypatch) -> None:
    from aip.integration.bccr.providers import urllib_http_provider as provider_module

    class StubProvider:
        def get(self, url, *, timeout, headers):
            assert headers["Authorization"] == "Bearer TEST_ONLY"
            assert "fechaInicio=" in url and "fechainicio=" not in url
            if "/cuadro/1/series" in url:
                return {"status_code": 500, "body": {"estado": False}}
            assert "/indicadoresEconomicos/317/series" in url
            return {
                "status_code": 200,
                "body": {
                    "estado": True,
                    "datos": [
                        {
                            "codigoIndicador": "317",
                            "series": [
                                {"fecha": "2026-10-14", "valorDatoPorPeriodo": 450.0}
                            ],
                        }
                    ],
                },
            }

    monkeypatch.setattr(provider_module, "UrllibHTTPProvider", StubProvider)
    monkeypatch.setattr(check, "UrllibHTTPProvider", StubProvider)
    config = SimpleNamespace(token="TEST_ONLY", base_url="https://apim.bccr.fi.cr")
    chart = check._bccr_probe(config, target_date=date(2026, 10, 14))
    single = check._bccr_probe(
        config, target_date=date(2026, 10, 14), indicator_code="317"
    )
    assert "BCCR cuadro 1: HTTP 500" in chart
    assert "BCCR indicador 317: HTTP 200; 1 obs; último 2026-10-14" in single
    assert "450.0" not in single
    assert "TEST_ONLY" not in chart + single
