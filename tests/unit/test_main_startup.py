from __future__ import annotations

import sys
import types

import aip.main
from aip.core.startup_timing import StartupTimer


def test_configured_preflight_failure_stops_before_ui_import(monkeypatch) -> None:
    monkeypatch.setenv("AIP_EXECUTION_MODE", "CONFIGURED")

    import aip.tools.preflight_runtime as preflight_runtime

    monkeypatch.setattr(preflight_runtime, "main", lambda _argv=None: 17)
    sys.modules.pop("aip.ui.application.main", None)

    assert aip.main.main([]) == 17
    assert "aip.ui.application.main" not in sys.modules


def test_configured_preflight_success_launches_ui_in_same_process(monkeypatch) -> None:
    monkeypatch.setenv("AIP_EXECUTION_MODE", "CONFIGURED")

    import aip.tools.preflight_runtime as preflight_runtime

    monkeypatch.setattr(preflight_runtime, "main", lambda _argv=None: 0)

    captured: dict[str, object] = {}
    fake_ui_main = types.ModuleType("aip.ui.application.main")

    def _fake_main(argv=None, *, startup_timer=None) -> int:
        captured["argv"] = argv
        captured["startup_timer"] = startup_timer
        return 23

    fake_ui_main.main = _fake_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aip.ui.application.main", fake_ui_main)

    assert aip.main.main(["--example"]) == 23
    assert captured["argv"] == ["--example"]
    assert isinstance(captured["startup_timer"], StartupTimer)
