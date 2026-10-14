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
    assert 'call "scripts\\launch\\load_existing_institutional_runtime.cmd"' in launcher
    assert 'set "AIP_EXECUTION_MODE=CONFIGURED"' in launcher
    assert 'set "AIP_DEMO_MODE_ENABLED=false"' in launcher
    assert "python -m aip" in launcher
    assert "exit /b %AIP_CONFIGURED_EXIT%" in launcher


def test_existing_private_runtime_resolver_uses_safe_precedence() -> None:
    loader = Path("scripts/launch/load_existing_institutional_runtime.cmd").read_text(
        encoding="utf-8"
    )
    explicit = loader.index("if defined AIP_RUNTIME_LOCAL_CMD (")
    preview = loader.index('if exist "config\\runtime.local.cmd" (')
    inherited = loader.index("if defined AIP_BCCR_TOKEN (")
    certified = loader.index(
        'if exist "C:\\Proyectos\\AIP-TIR5-RC1\\AIP-Enterprise-release-core-v1.0'
        '\\config\\runtime.local.cmd" ('
    )
    assert explicit < preview < inherited < certified
    assert 'call "%AIP_RUNTIME_LOCAL_CMD%"' in loader
    assert 'call "config\\runtime.local.cmd"' in loader
    assert "exit /b 2" in loader
    assert "set AIP_BCCR_TOKEN=" not in loader
    assert "\ncopy " not in loader.lower()
    for diagnostic in ("DIAGNOSTICAR_BCCR_SUGEF.cmd", "AUDITAR_FUENTES_CONFIGURADAS.cmd"):
        text = Path(diagnostic).read_text(encoding="utf-8")
        assert 'call "scripts\\launch\\load_existing_institutional_runtime.cmd"' in text
