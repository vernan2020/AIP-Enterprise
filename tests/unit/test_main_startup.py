from __future__ import annotations

import sys
import types

import aip.main


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

    fake_ui_main = types.ModuleType("aip.ui.application.main")
    fake_ui_main.main = lambda argv=None: 23  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aip.ui.application.main", fake_ui_main)

    assert aip.main.main(["--example"]) == 23
