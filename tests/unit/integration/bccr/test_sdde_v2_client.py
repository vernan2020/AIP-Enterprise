"""New real SDDE contract tested with simulated HTTP, never real credentials."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.integration.bccr.connector.sdde_v2_client import SDDEv2Client
from aip.integration.bccr.providers.sdde_v2_http_provider import SDDEv2HTTPProvider


def _client(handler, *, token="PRIVATE.TEST.SIGNATURE", retries=0) -> SDDEv2Client:
    return SDDEv2Client(
        config=BCCRConfig(
            token=token,
            name="Cuenta institucional",
            email="usuario@example.invalid",
            retry_attempts=retries,
        ),
        provider=SDDEv2HTTPProvider(transport=httpx.MockTransport(handler)),
    )


def test_bccr_sdde_v2_uses_saved_account_and_bearer_only_on_official_rest_get() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "estado": True,
                "mensaje": "Consulta exitosa",
                "datos": [
                    {
                        "codigoIndicador": "317",
                        "series": [
                            {"fecha": "2026-10-15", "valorDatoPorPeriodo": 453.75}
                        ],
                    }
                ],
            },
        )

    client = _client(handler)
    try:
        response = client.fetch_series(
            indicator_code="317", from_date="2026/10/01", to_date="2026/10/15"
        )
        assert response["body"]["datos"][0]["series"][0]["valorDatoPorPeriodo"] == 453.75
        assert len(requests) == 1
        request = requests[0]
        assert request.method == "GET"
        assert request.url.host == "apim.bccr.fi.cr"
        assert request.url.path.endswith("/indicadoresEconomicos/317/series")
        assert parse_qs(urlsplit(str(request.url)).query) == {
            "fechaInicio": ["2026/10/01"],
            "fechaFin": ["2026/10/15"],
            "idioma": ["ES"],
        }
        assert request.headers["Authorization"] == "Bearer PRIVATE.TEST.SIGNATURE"
        assert request.headers["Accept"] == "application/json"
        assert "Cuenta institucional" not in str(request.url)
        assert "usuario@example.invalid" not in str(request.url)
        assert "PRIVATE.TEST.SIGNATURE" not in str(request.url)
        assert "content-type" not in request.headers
        assert client._provider._client.is_closed is False
    finally:
        client.close()
    assert client._provider._client.is_closed is True


@pytest.mark.parametrize(
    ("from_date", "to_date", "code"),
    [
        ("15/10/2026", "2026/10/15", "317"),
        ("2026/10/16", "2026/10/15", "317"),
        ("2026/10/01", "2026/10/15", "../318"),
        ("2026/10/01", "2026/10/15", "0"),
    ],
)
def test_bccr_v2_rejects_invalid_parameters_before_network(
    from_date, to_date, code
) -> None:
    client = _client(lambda _req: pytest.fail("Network should not be called"))
    try:
        with pytest.raises(ValueError):
            client.fetch_series(
                indicator_code=code, from_date=from_date, to_date=to_date
            )
    finally:
        client.close()


@pytest.mark.parametrize("origin", ["http://apim.bccr.fi.cr", "https://evil.invalid", "https://apim.bccr.fi.cr@evil.invalid", "https://apim.bccr.fi.cr/path"])
def test_sdde_v2_rejects_non_official_hosts_and_non_https(origin) -> None:
    with pytest.raises(ValueError, match="official HTTPS"):
        SDDEv2Client(config=BCCRConfig(base_url=origin, token="FAKE"))


@pytest.mark.parametrize("status", [301, 401, 403, 404, 500])
def test_sdde_v2_fails_closed_with_redacted_http_errors(status: int) -> None:
    client = _client(
        lambda request: httpx.Response(
            status,
            headers={"Location": "https://evil.invalid/"},
            text="secret=PRIVATE.TEST.SIGNATURE",
        ),
        retries=2,
    )
    try:
        with pytest.raises(ConnectionError, match=f"HTTP {status}") as error:
            client.fetch_series(
                indicator_code="317", from_date="2026/10/01", to_date="2026/10/15"
            )
        assert "PRIVATE.TEST.SIGNATURE" not in str(error.value)
    finally:
        client.close()


@pytest.mark.parametrize("body", [{"estado": False, "datos": []}, {"estado": True, "datos": {}}, {"status": "ok"}])
def test_sdde_v2_rejects_false_success_and_malformed_payload(body: dict) -> None:
    client = _client(lambda request: httpx.Response(200, json=body))
    try:
        with pytest.raises(ValueError, match="BCCR SDDE"):
            client.fetch_series(
                indicator_code="317", from_date="2026/10/01", to_date="2026/10/15"
            )
    finally:
        client.close()


def test_sdde_v2_retries_429_then_reuses_successful_transport(monkeypatch) -> None:
    import aip.integration.bccr.connector.sdde_v2_client as module

    monkeypatch.setattr(module.time, "sleep", lambda _delay: None)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"estado": True, "datos": []})

    client = _client(handler, retries=1)
    try:
        result = client.fetch_series(
            indicator_code="318", from_date="2026/10/01", to_date="2026/10/15"
        )
        assert result["body"]["estado"] is True
        assert len(calls) == 2
    finally:
        client.close()


def test_sdde_v2_supports_chart_series_with_same_authentication() -> None:
    request_paths = []

    def handler(request):
        request_paths.append(request.url.path)
        return httpx.Response(200, json={"estado": True, "datos": []})

    client = _client(handler)
    try:
        assert client.fetch_chart_series(
            chart_code="1", from_date="2026/10/01", to_date="2026/10/15"
        )["status_code"] == 200
        assert request_paths[0].endswith("/cuadro/1/series")
    finally:
        client.close()
