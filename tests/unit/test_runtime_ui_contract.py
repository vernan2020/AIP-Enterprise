from __future__ import annotations

from pathlib import Path

from scripts.recovery.verify_release_ui_contract import verify_runtime_ui_contract


def test_release_source_satisfies_portfolio_ui_contract() -> None:
    root = Path(__file__).resolve().parents[2]

    assert verify_runtime_ui_contract(root) == ()


def test_configured_launcher_blocks_legacy_restore_inside_git_checkout() -> None:
    root = Path(__file__).resolve().parents[2]
    launcher = (root / "run_aip_configured.cmd").read_text(encoding="utf-8")

    git_guard = launcher.index('if exist ".git\\" (')
    restore = launcher.index("restore_runtime_checkpoint.py")

    assert git_guard < restore
    assert "verify_release_ui_contract.py" in launcher
