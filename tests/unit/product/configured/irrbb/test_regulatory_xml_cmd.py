from __future__ import annotations

from pathlib import Path


def test_regulatory_xml_readiness_launcher_is_real_configured_read_only() -> None:
    root = Path(__file__).resolve().parents[5]
    launcher = (root / "DIAGNOSTICAR_RTILB_XML.cmd").read_text(encoding="utf-8")
    assert 'set "AIP_EXECUTION_MODE=CONFIGURED"' in launcher
    assert 'set "AIP_DEMO_MODE_ENABLED=false"' in launcher
    assert "regulatory_xml_readiness_cli %*" in launcher
    assert "config\\runtime.local.cmd" in launcher
    assert "AIP_XML_CONFIA_ROOT=" not in launcher
    assert "restore_runtime_checkpoint.py" not in launcher
    assert "duckdb" not in launcher.casefold()
