from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_show_ruff_import_fix_for_portfolio_history(tmp_path: Path) -> None:
    source = Path(
        "src/aip/product/configured/services/configured_portfolio_history_service.py"
    )
    candidate = tmp_path / source.name
    shutil.copy2(source, candidate)
    result = subprocess.run(
        ["ruff", "check", "--select", "I001", "--fix", "--diff", str(candidate)],
        check=False,
        capture_output=True,
        text=True,
    )
    raise AssertionError(result.stdout or result.stderr or "Ruff produced no diff")
