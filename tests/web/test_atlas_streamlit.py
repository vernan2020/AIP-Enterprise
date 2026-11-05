import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ticotrader_streamlit.access import authorize
from ticotrader_streamlit.jobs import Jobs, isolated
from ticotrader_streamlit.worker import personal_source
from ticotrader_web.runtime import Runtime


def claims(**changes):
    return dict(
        is_logged_in=True,
        email="a@example.com",
        email_verified=True,
        iss="https://accounts.google.com",
        aud="client",
        exp=200,
        **changes,
    )


def test_access_fails_closed():
    settings = dict(allowed_emails=["a@example.com"], admin_emails=["a@example.com"])
    assert authorize(claims(), settings, "client", now=100) == ("a@example.com", True)
    for patch in (
        {"exp": 99},
        {"exp": float("nan")},
        {"email_verified": False},
        {"email": "b@example.com"},
        {"aud": "other"},
        {"is_logged_in": False},
    ):
        with pytest.raises(PermissionError):
            authorize({**claims(), **patch}, settings, "client", now=100)
    with pytest.raises(ValueError):
        authorize(claims(), {"allowed_emails": [str(i) for i in range(21)]}, "client")


@pytest.mark.parametrize("users", [5, 10, 20])
def test_shared_queries_are_computed_once_and_access_is_scoped(users):
    release = threading.Event()
    calls = []

    def runner(query, settings):
        calls.append(query)
        release.wait(5)
        return {"status": "AVAILABLE"}

    queue = Jobs({}, runner=runner)
    try:
        with ThreadPoolExecutor(max_workers=users) as pool:
            ids = list(pool.map(lambda i: queue.submit(str(i), {"kind": "forecast"}), range(users)))
        assert len(set(ids)) == 1
        release.set()
        queue.close()
        assert len(calls) == 1
        for i in range(users):
            assert queue.read(str(i), ids[i])["status"] == "done"
        with pytest.raises(KeyError):
            queue.read("outsider", ids[0])
        with pytest.raises(PermissionError):
            queue.submit("0", {"kind": "macro", "refresh": True})
    finally:
        release.set()
        queue.close()


def test_timed_out_process_is_terminated_and_next_job_can_run():
    slow = [sys.executable, "-c", "import sys,time;sys.stdin.read();time.sleep(10)"]
    quick = [
        sys.executable,
        "-c",
        'import sys,pathlib;sys.stdin.read();pathlib.Path(sys.argv[1]).write_text(\'{"data":{"status":"AVAILABLE"}}\')',
    ]
    with pytest.raises(TimeoutError):
        isolated({}, {}, timeout=0.2, command=slow)
    assert isolated({}, {}, timeout=10, command=quick)["status"] == "AVAILABLE"


def test_personal_config_never_reads_institutional_token(monkeypatch):
    monkeypatch.setenv("AIP_BCCR_TOKEN", "institutional-do-not-use")
    runtime = Runtime(source_config=personal_source({"token": "personal-only"}))
    from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig

    source = runtime.factory.container.resolve(ConfiguredSourceConfig)
    assert source.bccr.token == "personal-only"
    assert not source.sql_server.enabled
    assert personal_source({}).bccr.token is None


def test_streamlit_without_secrets_stops_before_queries():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(Path("ticotrader_streamlit/app.py").resolve()).run(timeout=15)
    assert not app.exception
    assert "configuración privada" in app.info[0].value


def test_selected_forecast_download_preserves_official_rows(monkeypatch, tmp_path):
    from datetime import date
    from decimal import Decimal

    from aip.domain.economic.economic_indicator_observation import EconomicIndicatorObservation
    from aip.integration.bccr.connector.sdde_v2_client import SDDEv2Client
    from aip.integration.bccr.normalization.economic_series_parser import BCCREconomicSeriesParser
    from ticotrader_streamlit import history

    calls = []

    def fetch(self, **kwargs):
        calls.append(kwargs)
        return {"body": {}}

    monkeypatch.setattr(history, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(SDDEv2Client, "fetch_series", fetch)
    monkeypatch.setattr(
        BCCREconomicSeriesParser,
        "parse",
        lambda self, body: (
            EconomicIndicatorObservation(
                "TBP", date(2026, 9, 30), Decimal("3.5"), "BCCR", "%", "423"
            ),
            EconomicIndicatorObservation(
                "TPM", date(2026, 9, 30), Decimal("3"), "BCCR", "%", "3541"
            ),
        ),
    )
    service = history.forecast_service({"token": "test-only", "email": "test@example.com"}, "TBP")
    assert len(calls) == 1
    assert calls[0]["indicator_code"] == "423"
    assert len(service._repository.get_series("TBP").observations) == 1
    assert service._repository.get_series("TPM").observations == ()
    service._repository.store.close()


@pytest.mark.parametrize("kind", ["financial", "macro", "forecast", "compare", "projection"])
def test_streamlit_empty_source_views_render_without_fabricated_values(kind):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_string(
        f"from ticotrader_streamlit.views import show\nshow({{'status':'UNAVAILABLE'}}, {kind!r})"
    ).run(timeout=15)
    assert not app.exception
    assert len(app.get("download_button")) == 2


def test_twenty_distinct_forecasts_never_compute_in_parallel():
    from ticotrader_web.forecast_policy import FORECAST_INDICATORS

    lock = threading.Lock()
    active = 0
    peak = 0
    calls = 0

    def runner(query, settings):
        nonlocal active, peak, calls
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.01)
        with lock:
            active -= 1
            calls += 1
        return {"status": "AVAILABLE"}

    queue = Jobs({}, runner=runner)
    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            list(
                pool.map(
                    lambda i: queue.submit(
                        str(i), {"kind": "forecast", "indicator": FORECAST_INDICATORS[i]}
                    ),
                    range(20),
                )
            )
    finally:
        queue.close()
    assert calls == 20
    assert peak == 1


def test_authorized_reader_sees_pages_without_admin_controls(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from ticotrader_streamlit import catalog

    monkeypatch.setattr(catalog, "load_entities", lambda: {"123": "Entidad de prueba"})
    source = """
import runpy
import time
import streamlit as st
class Identity(dict):
    @property
    def is_logged_in(self):
        return True
st.user = Identity(is_logged_in=True, email='reader@example.com', email_verified=True,
    iss='https://accounts.google.com', aud='client', exp=time.time()+3600)
runpy.run_path('ticotrader_streamlit/app.py')
"""
    app = AppTest.from_string(source)
    app.secrets["auth"] = {"client_id": "client"}
    app.secrets["atlas"] = {
        "allowed_emails": ["reader@example.com", "admin@example.com"],
        "admin_emails": ["admin@example.com"],
    }
    app.run(timeout=15)
    assert not app.exception
    assert "Administración" not in app.radio[0].options
    assert len(app.checkbox) == 0
    app.radio[0].set_value("Forecast Lab").run()
    assert not app.exception
    assert app.selectbox[0].value == "TBP"
    app.radio[0].set_value("Comparativo histórico").run()
    assert not app.exception
    assert app.multiselect[0].options == ["Entidad de prueba"]
    assert not app.text_input
    assert "Activos" in app.selectbox[0].options
    assert "ROE" in app.selectbox[0].options
    assert "job_financial" not in app.session_state


def test_real_isolated_forecast_without_token_returns_no_fabricated_projection():
    from ticotrader_web.app import Query

    result = isolated(Query(kind="forecast").model_dump(mode="json"), {}, timeout=30)
    assert result["status"] != "AVAILABLE"
    assert not result["points"]


def test_entity_catalog_preserves_codes_and_rejects_incomplete_rows():
    from ticotrader_streamlit.catalog import entity_options

    assert entity_options(
        [
            {"codigoEntidad": "002", "nombreEntidad": "Entidad Z"},
            {"codigoEntidad": "001", "nombreEntidad": "Entidad A"},
            {"codigoEntidad": "003"},
            {"nombreEntidad": "Sin código"},
        ]
    ) == {"001": "Entidad A", "002": "Entidad Z"}


def test_comparison_series_match_engine_definitions():
    from aip.domain.financial_analysis.financial_metric_history import FinancialMetricHistoryService
    from ticotrader_streamlit.catalog import COMPARISON_SERIES

    assert COMPARISON_SERIES == {
        code: label for code, label, _unit in FinancialMetricHistoryService._DEFINITIONS
    }
