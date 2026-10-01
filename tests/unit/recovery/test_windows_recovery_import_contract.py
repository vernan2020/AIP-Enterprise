from __future__ import annotations

import inspect
from pathlib import Path

from aip.integration.bccr.connector.cache import BCCRCache
from scripts.recovery.apply_windows_recovery import _runtime_validation_env


def test_bccr_cache_supports_per_entry_ttl() -> None:
    params = inspect.signature(BCCRCache.set).parameters

    assert "ttl_seconds" in params


def test_runtime_validation_env_prioritizes_absolute_project_src(tmp_path: Path) -> None:
    project = tmp_path / "AIP Enterprise"
    (project / "src").mkdir(parents=True)

    env = _runtime_validation_env(project)

    assert Path(env["PYTHONPATH"]).is_absolute()
    assert Path(env["PYTHONPATH"]) == (project / "src").resolve()
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
