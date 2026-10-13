"""The V4.5.1 Windows entry point runs the real institutional AIP."""

from __future__ import annotations

from pathlib import Path


def test_windows_v451_launcher_uses_only_configured_runtime() -> None:
    launcher = Path("run_aip_ux_preview.cmd").read_text(encoding="utf-8")
    assert "call run_aip_configured.cmd" in launcher
    assert "AIP_RUNTIME_LOCAL_CMD" in launcher
    assert "AIP_EXECUTION_MODE=DEMO" not in launcher
    assert "AIP_DEMO_MODE_ENABLED=true" not in launcher
    assert ":demo" not in launcher.lower()


def test_configured_entrypoint_reuses_existing_local_configuration() -> None:
    launcher = Path("run_aip_configured.cmd").read_text(encoding="utf-8")
    assert "if defined AIP_RUNTIME_LOCAL_CMD (" in launcher
    assert 'call "%AIP_RUNTIME_LOCAL_CMD%"' in launcher
    assert 'if exist "config\\runtime.local.cmd" call "config\\runtime.local.cmd"' in launcher
    assert 'set "AIP_EXECUTION_MODE=CONFIGURED"' in launcher
    assert 'set "AIP_DEMO_MODE_ENABLED=false"' in launcher
    assert "python -m aip" in launcher
    assert "exit /b %AIP_CONFIGURED_EXIT%" in launcher
