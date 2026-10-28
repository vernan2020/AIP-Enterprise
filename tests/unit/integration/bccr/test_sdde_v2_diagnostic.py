"""Credential-safe BCCR v2 diagnostics tested without accessing the internet."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import aip.integration.bccr.connector.sdde_v2_diagnostic as diagnostic


def test_sdde_v2_dry_run_consumes_registered_identity_without_printing_it(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    token = "SECRET.TEST.JWT"
    account = "usuario.bccr@company.invalid"
    settings = SimpleNamespace(
        enabled=True,
        base_url="https://apim.bccr.fi.cr",
        token=token,
        name="Cuenta SDDE",
        email=account,
        timeout_seconds=10.0,
        retries=1,
    )
    monkeypatch.setattr(
        diagnostic,
        "EnvironmentLoader",
        lambda: SimpleNamespace(load_source_config=lambda: SimpleNamespace(bccr=settings)),
    )

    class StubClient:
        def __init__(self, *, config):
            assert config.token == token
            assert config.email == account
            assert config.name == "Cuenta SDDE"

        def close(self):
            pass

    monkeypatch.setattr(diagnostic, "SDDEv2Client", StubClient)
    assert diagnostic.run(["--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "READY_FOR_LIVE_TEST" in output
    assert '"name_configured": true' in output
    assert '"email_configured": true' in output
    assert token not in output
    assert account not in output


def test_sdde_v2_diagnostic_validates_real_response_metadata() -> None:
    result = diagnostic._latest_valid_observation(
        {
            "body": {
                "datos": [
                    {
                        "codigoIndicador": "317",
                        "series": [
                            {"fecha": "2026-09-13", "valorDatoPorPeriodo": "453.00"},
                            {"fecha": "2026-09-14", "valorDatoPorPeriodo": "456.15"},
                        ],
                    }
                ]
            }
        },
        "317",
    )
    assert result == {"date": "2026-09-14", "value": "456.15"}
    assert diagnostic._latest_valid_observation({"body": {"datos": []}}, "317") is None


def test_bccr_v2_launcher_preserves_private_config_and_exit_code() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    cmd = (root / "DIAGNOSTICAR_BCCR_V2.cmd").read_text(encoding="utf-8")
    assert 'set "AIP_EXECUTION_MODE=CONFIGURED"' in cmd
    assert "sdde_v2_diagnostic %*" in cmd
    assert "config\\runtime.local.cmd" in cmd
    assert "AIP_BCCR_TOKEN" not in cmd
    assert "echo BCCR SDDE v2" in cmd


def test_bccr_v2_live_diagnostic_reports_latency_and_window_without_secrets(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    settings = SimpleNamespace(
        enabled=True, base_url="https://apim.bccr.fi.cr",
        token="SECRET.TOKEN", name="Private account", email="private@example.invalid",
        timeout_seconds=5.0, retries=0,
    )
    monkeypatch.setattr(
        diagnostic, "EnvironmentLoader",
        lambda: SimpleNamespace(load_source_config=lambda: SimpleNamespace(bccr=settings)),
    )

    class StubClient:
        def __init__(self, *, config):
            assert config.token == "SECRET.TOKEN"

        def fetch_series(self, *, indicator_code, from_date, to_date):
            assert indicator_code == "317"
            assert from_date <= to_date
            return {"body": {"datos": [{"codigoIndicador": "317", "series": [
                {"fecha": diagnostic.date.today().isoformat(), "valorDatoPorPeriodo": "449.12"}
            ]}]}}

        def close(self):
            pass

    monkeypatch.setattr(diagnostic, "SDDEv2Client", StubClient)
    assert diagnostic.run(["--codes", "317", "--days", "20"]) == 0
    output = capsys.readouterr().out
    import json
    report = json.loads(output)
    assert report["status"] == "LIVE_OK"
    assert report["window"]["to"] == diagnostic.date.today().strftime("%Y/%m/%d")
    assert report["indicators"][0]["elapsed_ms"] >= 0
    assert "SECRET.TOKEN" not in output
    assert "private@example.invalid" not in output


def test_bccr_v2_http_500_diagnostic_includes_latency_and_redacted_status(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    settings = SimpleNamespace(
        enabled=True, base_url="https://apim.bccr.fi.cr",
        token="SECRET.TOKEN", name="Account", email="private@example.invalid",
        timeout_seconds=5.0, retries=0,
    )
    monkeypatch.setattr(
        diagnostic, "EnvironmentLoader",
        lambda: SimpleNamespace(load_source_config=lambda: SimpleNamespace(bccr=settings)),
    )

    class StubClient:
        def __init__(self, *, config):
            pass

        def fetch_series(self, **kwargs):
            raise ConnectionError("BCCR SDDE HTTP 500 on indicator request")

        def close(self):
            pass

    monkeypatch.setattr(diagnostic, "SDDEv2Client", StubClient)
    assert diagnostic.run(["--codes", "317"]) == 2
    import json
    report = json.loads(capsys.readouterr().out)
    item = report["indicators"][0]
    assert item["status"] == "HTTP_ERROR"
    assert item["http_status"] == "500"
    assert item["elapsed_ms"] >= 0
