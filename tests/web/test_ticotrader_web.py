import hashlib
import io
import time
from datetime import date
from decimal import Decimal
from threading import RLock

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from ticotrader_web.app import clean, create_app


class RuntimeStub:
    lock = RLock()

    def financial(self, *args):
        self.args = args
        return {
            "status": "AVAILABLE",
            "cutoff_date": "2026-09-30",
            "statement_rows": [{"account_name": '=HYPERLINK("bad")', "amount": "100"}],
            "metric_history": [
                {
                    "label": "Activos",
                    "points": [
                        {"iso_date": "2026-08-31", "value": 12},
                        {"iso_date": "2026-09-30", "value": 14},
                    ],
                }
            ],
        }

    def compare(self, *args):
        self.args = args
        return {"entities": []}

    def macro(self, *args):
        return {"status": "UNAVAILABLE", "market_snapshot": []}

    def projection(self):
        return {"status": "UNAVAILABLE", "rows": []}

    def forecast(self, *args):
        return {"status": "UNAVAILABLE", "points": []}


@pytest.fixture
def client(monkeypatch):
    salt = b"1234567890123456"
    password = "test-password-12345"
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000).hex()
    monkeypatch.setenv("TICOTRADER_USERNAME", "analyst")
    monkeypatch.setenv("TICOTRADER_PASSWORD_HASH", f"pbkdf2_sha256$600000${salt.hex()}${digest}")
    monkeypatch.setenv("TICOTRADER_COOKIE_SECURE", "false")
    runtime = RuntimeStub()
    app = create_app(runtime)
    with TestClient(app) as c:
        c.runtime = runtime
        yield c
    app.state.executor.shutdown(wait=True)


def login(client):
    r = client.post("/api/login", json={"username": "analyst", "password": "test-password-12345"})
    assert r.status_code == 200
    client.headers["x-csrf-token"] = r.json()["csrf"]


def complete(client, body):
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 200, r.text
    key = r.json()["id"]
    for _ in range(100):
        response = client.get("/api/jobs/" + key).json()
        if response["status"] != "running":
            return key, response
        time.sleep(0.01)
    pytest.fail("job did not complete")


def test_private_endpoints_and_csrf(client):
    assert client.get("/api/session").status_code == 401
    assert client.post("/api/jobs", json={"kind": "macro"}).status_code == 401
    login(client)
    client.headers.pop("x-csrf-token")
    assert client.post("/api/jobs", json={"kind": "macro"}).status_code == 403


def test_no_authentication_default(monkeypatch):
    monkeypatch.delenv("TICOTRADER_USERNAME", raising=False)
    monkeypatch.delenv("TICOTRADER_PASSWORD_HASH", raising=False)
    with TestClient(create_app(RuntimeStub())) as c:
        assert c.post("/api/login", json={"username": "a", "password": "b"}).status_code == 503


def test_financial_cutoff_passed_and_xlsx_real(client):
    login(client)
    key, response = complete(
        client, {"kind": "financial", "entity_id": "123", "cutoff": "2026-09-30", "refresh": True}
    )
    assert response["data"]["status"] == "AVAILABLE"
    assert client.runtime.args == ("123", date(2026, 9, 30), True)
    xlsx = client.get(f"/api/jobs/{key}/export?format=xlsx")
    wb = load_workbook(io.BytesIO(xlsx.content))
    assert wb["statement_rows"]["A2"].value.startswith("'=")
    assert wb["Serie 1"]["B2"].value == 12
    assert len(wb["Serie 1"]._charts) == 1
    csv = client.get(f"/api/jobs/{key}/export?format=csv")
    assert "'=HYPERLINK" in csv.text


@pytest.mark.parametrize("kind", ["macro", "projection", "forecast"])
def test_unavailable_is_not_zero_or_demo(client, kind):
    login(client)
    _, r = complete(client, {"kind": kind})
    assert r["data"]["status"] == "UNAVAILABLE"


def test_comparison_validation(client):
    login(client)
    for body in (
        {"kind": "compare"},
        {"kind": "compare", "entity_ids": ["1"] * 6},
        {"kind": "compare", "entity_ids": ["1"], "horizon": "CUSTOM"},
        {
            "kind": "compare",
            "entity_ids": ["1"],
            "custom_from": "2026-10-01",
            "custom_to": "2026-09-01",
        },
    ):
        assert client.post("/api/jobs", json=body).status_code == 422
    _, r = complete(
        client,
        {"kind": "compare", "entity_ids": ["1", "2"], "series_code": "ROA", "horizon": "12M"},
    )
    assert client.runtime.args[:3] == (["1", "2"], "ROA", "12M")


def test_session_isolation_and_logout(client):
    login(client)
    key, _ = complete(client, {"kind": "macro"})
    client.cookies.clear()
    login(client)
    assert client.get("/api/jobs/" + key).status_code == 404
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/session").status_code == 401


def test_login_rate_limit_and_origin(client):
    assert (
        client.post(
            "/api/login",
            headers={"Origin": "https://evil.example"},
            json={"username": "a", "password": "b"},
        ).status_code
        == 403
    )
    for _ in range(5):
        assert client.post("/api/login", json={"username": "a", "password": "b"}).status_code == 401
    assert client.post("/api/login", json={"username": "a", "password": "b"}).status_code == 429


def test_response_headers_and_assets(client):
    r = client.get("/")
    assert "TicoTrader" in r.text
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/logo.svg").status_code == 200
    assert client.get("/docs").status_code == 404


def test_serialization_precision():
    assert clean(
        {"x": Decimal("123456789.123456789"), "date": date(2026, 9, 30), "n": float("nan")}
    ) == {"x": "123456789.123456789", "date": "2026-09-30", "n": None}


def test_original_runtime_import_and_configuration():
    from ticotrader_web.runtime import Runtime

    factory = Runtime().factory
    assert factory.config.execution_mode == "CONFIGURED"
    assert not factory.config.demo_mode_enabled
    assert not factory.configured_source_config.folder_watch.enabled
    assert not factory.configured_source_config.sql_server.enabled


def test_personal_token_is_private_and_redacted(client, monkeypatch, tmp_path):
    from ticotrader_web import connections

    monkeypatch.setenv("TICOTRADER_CONNECTIONS_FILE", str(tmp_path / "connections.json"))
    assert client.get("/api/connections").status_code == 401
    login(client)
    token = "private-token-test-12345"
    result = client.post(
        "/api/connections/bccr", json={"token": token, "email": "user@example.com"}
    )
    assert result.status_code == 200
    assert result.json()["bccr_token_configured"]
    assert token not in result.text
    assert token not in client.get("/api/connections").text
    assert connections.read()["bccr_token"] == token
    assert connections.redact({"diagnostics": ["failed with " + token]}) == {
        "diagnostics": ["failed with [CREDENCIAL OCULTA]"]
    }
    assert (tmp_path / "connections.json").stat().st_mode & 0o077 == 0
