from __future__ import annotations

from aip.core.startup_timing import StartupTimer
from aip.ui.services.diagnostic_service import DiagnosticMetricsStore


def test_startup_timer_records_named_stages() -> None:
    timer = StartupTimer()

    with timer.stage("preflight"):
        pass
    with timer.stage("window_create"):
        pass

    snapshot = timer.snapshot()

    assert snapshot.total_ms >= 0.0
    assert set(snapshot.stages_ms) == {"preflight", "window_create"}
    assert snapshot.stages_ms["preflight"] >= 0.0
    assert snapshot.stages_ms["window_create"] >= 0.0


def test_startup_profile_flag_is_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("AIP_PROFILE_STARTUP", raising=False)
    assert StartupTimer.profile_enabled() is False

    monkeypatch.setenv("AIP_PROFILE_STARTUP", "true")
    assert StartupTimer.profile_enabled() is True


def test_diagnostic_store_retains_startup_breakdown() -> None:
    store = DiagnosticMetricsStore()
    store.record_startup_metrics(
        {
            "total_ms": 1250.5,
            "stages_ms": {
                "configured_preflight": 100.0,
                "desktop_ui_import": 250.0,
                "window_create": 900.5,
            },
        }
    )

    snapshot = store.snapshot()

    assert snapshot["startup_time_ms"] == 1250.5
    assert snapshot["startup_stages_ms"] == {
        "configured_preflight": 100.0,
        "desktop_ui_import": 250.0,
        "window_create": 900.5,
    }
