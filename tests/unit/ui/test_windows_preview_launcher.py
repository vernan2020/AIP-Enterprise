"""The user-facing Windows preview must never substitute synthetic data by default."""

from __future__ import annotations

from pathlib import Path


def test_windows_preview_uses_configured_runtime_by_default() -> None:
    source = Path("run_aip_ux_preview.cmd").read_text(encoding="utf-8")
    before_demo = source.split("\n:demo\n", 1)[0]
    assert 'if /I "%~1"=="demo" goto demo' in before_demo
    assert "call run_aip_configured.cmd" in before_demo
    assert 'set "AIP_EXECUTION_MODE=DEMO"' not in before_demo
    assert 'set "AIP_DEMO_MODE_ENABLED=true"' not in before_demo
    assert "config\\runtime.local.cmd" in before_demo


def test_windows_preview_requires_explicit_demo_argument() -> None:
    source = Path("run_aip_ux_preview.cmd").read_text(encoding="utf-8")
    demo_section = source.split("\n:demo\n", 1)[1]
    assert 'set "AIP_EXECUTION_MODE=DEMO"' in demo_section
    assert 'set "AIP_DEMO_MODE_ENABLED=true"' in demo_section
    assert 'set "AIP_SQLSERVER_ENABLED=false"' in demo_section
