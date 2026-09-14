from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


def _load_builder() -> ModuleType:
    module_path = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "recovery"
        / "build_windows_recovery_package.py"
    )
    spec = importlib.util.spec_from_file_location("build_windows_recovery_package", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Windows recovery package builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_commit_is_actual_github_checkout_sha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    builder = _load_builder()
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "pull_request": {
                    "head": {
                        "sha": "pr-head-that-is-not-the-merge-candidate",
                        "ref": "feature/example",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_SHA", "actual-checked-out-merge-candidate")

    assert builder._resolve_source_commit() == "actual-checked-out-merge-candidate"


def test_source_branch_uses_pull_request_head_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    builder = _load_builder()
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps({"pull_request": {"head": {"ref": "release/package-fix"}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_REF_NAME", "synthetic-merge-ref")

    assert builder._resolve_source_branch() == "release/package-fix"


def test_source_branch_falls_back_to_github_ref_name(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _load_builder()
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setenv("GITHUB_REF_NAME", "recovery/full-runtime-rc1-20260829")

    assert builder._resolve_source_branch() == "recovery/full-runtime-rc1-20260829"
