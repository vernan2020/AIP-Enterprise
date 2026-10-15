"""TicoTrader / AIP SDDE parity without relying on a real BCCR credential."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import httpx

from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.integration.bccr.connector.rest_client import BCCRRestClient
from aip.integration.bccr.providers.httpx_http_provider import HttpxHTTPProvider
from aip.integration.bccr.providers.select_official_transport import (
    select_official_bccr_transport,
)


def test_ticotrader_sdde_get_parity_keeps_dates_auth_and_json() -> None:
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "estado": True,
                "datos": [
                    {
                        "codigoIndicador": "317",
                        "series": [
                            {
                                "fecha": "2026-10-15",
                                "valorDatoPorPeriodo": "450.00",
                            }
                        ],
                    }
                ],
            },
        )

    provider = HttpxHTTPProvider(transport=httpx.MockTransport(handler))
    client = BCCRRestClient(
        config=BCCRConfig(
            token="TEST_HEADER.TEST_PAYLOAD.TEST_SIGNATURE",
            user_agent="TicoTrader-Portafolio360/1.0",
        ),
        provider=provider,
    )
    response = client.fetch_series(
        indicator_code="317", from_date="2026/09/01", to_date="2026/10/15"
    )

    assert response["status_code"] == 200
    assert response["body"]["datos"][0]["codigoIndicador"] == "317"
    assert len(captured) == 1
    request = captured[0]
    assert request.method == "GET"
    assert "/indicadoresEconomicos/317/series" in request.url.path
    assert parse_qs(urlsplit(str(request.url)).query) == {
        "fechaInicio": ["2026/09/01"],
        "fechaFin": ["2026/10/15"],
        "idioma": ["es"],
    }
    assert request.headers["authorization"] == "Bearer TEST_HEADER.TEST_PAYLOAD.TEST_SIGNATURE"
    assert request.headers["accept"] == "application/json"
    assert request.headers["user-agent"] == "TicoTrader-Portafolio360/1.0"
    assert "content-type" not in request.headers


def test_ticotrader_httpx_does_not_follow_redirects_or_expose_token() -> None:
    recorded = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(302, headers={"Location": "https://example.invalid/private"})

    client = BCCRRestClient(
        config=BCCRConfig(token="TEST_ONLY", retry_attempts=0),
        provider=HttpxHTTPProvider(transport=httpx.MockTransport(handler)),
    )
    try:
        client.fetch_series(indicator_code="317", from_date="2026/10/01", to_date="2026/10/15")
        assert False, "Expected a non-2xx failure"
    except ConnectionError as exc:
        assert "HTTP 302" in str(exc)
        assert "TEST_ONLY" not in str(exc)
    assert len(recorded) == 1


def test_official_transport_selector_prefers_httpx_and_keeps_urllib_fallback(
    monkeypatch,
) -> None:
    import aip.integration.bccr.providers.select_official_transport as selector

    assert isinstance(select_official_bccr_transport(), HttpxHTTPProvider)
    monkeypatch.setattr(selector, "find_spec", lambda _name: None)
    assert type(selector.select_official_bccr_transport()).__name__ == "UrllibHTTPProvider"
