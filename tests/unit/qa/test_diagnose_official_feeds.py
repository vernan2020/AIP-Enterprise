"""Official source smoke diagnostics must never disclose credentials."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from urllib.error import HTTPError

from scripts.qa import diagnose_official_feeds as check


def test_report_counts_are_read_only_and_schema_tolerant() -> None:
    assert check._records({"listaBalanzaComprobacionEntidad": [{"a": 1}]}, "listaBalanzaComprobacionEntidad") == 1
    assert check._records({"LISTABALANZACOMPROBACIONENTIDAD": [{"a": 1}]}, "listaBalanzaComprobacionEntidad") == 1
    assert check._records({"tieneError": True, "listaBalanzaComprobacionEntidad": [{}]}, "listaBalanzaComprobacionEntidad") == 0


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
                    "ReporteBalanceSituacionAnalisisFinancieroEntidad": "listaBalanceSituacionAnalisisFinancieroEntidad",
                    "ReporteEstadoResultadosAnalisisFinancieroEntidad": "listaEstadoResultadosAnalisisFinancieroEntidad",
                }[endpoint]: [{"periodo": "2026-09-01"}]
            }

    monkeypatch.setattr(check, "SUGEFFinancialApiClient", FakeClient)
    config = SimpleNamespace(enabled=True, api_enabled=True, api_entity_codes=("3004045138",), api_timeout_seconds=90, api_retries=2)
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
