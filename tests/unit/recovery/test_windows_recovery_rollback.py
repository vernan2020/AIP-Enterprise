from __future__ import annotations

from pathlib import Path

from scripts.recovery.apply_windows_recovery import (
    CERTIFIED_MARKER_NAME,
    _backup_project,
    _replace_src_transactionally,
    _restore_backup,
)

CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-final-20260829")


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_automatic_rollback_restores_pre_install_runtime(tmp_path: Path) -> None:
    project = tmp_path / "AIP"
    project.mkdir()

    original = {
        Path("src/aip/original.py"): "ORIGINAL_SRC\n",
        Path("run_aip_configured.cmd"): "ORIGINAL_LAUNCHER\n",
        Path("scripts/recovery/original.py"): "ORIGINAL_RECOVERY\n",
        CHECKPOINT_DIR / "MANIFEST.json": "ORIGINAL_CHECKPOINT\n",
        Path("config/runtime.local.cmd.example"): "ORIGINAL_EXAMPLE\n",
    }
    for relative, value in original.items():
        _write(project / relative, value)

    backup = _backup_project(project)
    assert backup.is_file()

    # Simulate a partially applied certified payload before validation fails.
    for relative in original:
        target = project / relative
        if target.exists():
            target.unlink()
    _write(project / "src/aip/new_runtime.py", "NEW_SRC\n")
    _write(project / "run_aip_configured.cmd", "NEW_LAUNCHER\n")
    _write(project / "scripts/recovery/new.py", "NEW_RECOVERY\n")
    _write(project / CHECKPOINT_DIR / "runtime_final.part000.b64", "NEW_CHECKPOINT\n")
    _write(project / "config/runtime.local.cmd.example", "NEW_EXAMPLE\n")
    _write(project / CERTIFIED_MARKER_NAME, "{}\n")

    _restore_backup(project, backup)

    for relative, expected in original.items():
        assert (project / relative).read_text(encoding="utf-8") == expected

    assert not (project / "src/aip/new_runtime.py").exists()
    assert not (project / "scripts/recovery/new.py").exists()
    assert not (project / CHECKPOINT_DIR / "runtime_final.part000.b64").exists()
    assert not (project / CERTIFIED_MARKER_NAME).exists()


def test_automatic_rollback_removes_files_absent_before_install(tmp_path: Path) -> None:
    project = tmp_path / "AIP"
    project.mkdir()
    _write(project / "src/aip/original.py", "ORIGINAL_SRC\n")

    backup = _backup_project(project)

    _write(project / "run_aip_configured.cmd", "NEW_LAUNCHER\n")
    _write(project / "scripts/recovery/new.py", "NEW_RECOVERY\n")
    _write(project / CHECKPOINT_DIR / "MANIFEST.json", "NEW_CHECKPOINT\n")
    _write(project / "config/runtime.local.cmd.example", "NEW_EXAMPLE\n")

    _restore_backup(project, backup)

    assert (project / "src/aip/original.py").read_text(encoding="utf-8") == "ORIGINAL_SRC\n"
    assert not (project / "run_aip_configured.cmd").exists()
    assert not (project / "scripts/recovery").exists()
    assert not (project / CHECKPOINT_DIR).exists()
    assert not (project / "config/runtime.local.cmd.example").exists()


def test_certified_src_install_never_renames_live_src(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "AIP"
    payload = tmp_path / "payload"
    _write(project / "src/aip/original.py", "ORIGINAL\n")
    _write(project / "src/aip/stale.py", "STALE\n")
    _write(payload / "src/aip/certified.py", "CERTIFIED\n")

    # Simulate a scratch directory left by an interrupted prior installer run.
    _write(project / ".aip_src_before_certified/aip/old.py", "OLD_SNAPSHOT\n")

    def _forbidden_rename(self: Path, target: Path) -> Path:
        raise AssertionError(f"live directory rename is forbidden: {self} -> {target}")

    monkeypatch.setattr(Path, "rename", _forbidden_rename)

    _replace_src_transactionally(payload, project)

    assert (project / "src/aip/certified.py").read_text(encoding="utf-8") == "CERTIFIED\n"
    assert not (project / "src/aip/original.py").exists()
    assert not (project / "src/aip/stale.py").exists()
    assert not (project / ".aip_src_before_certified").exists()


def test_certified_src_install_is_repeatable(tmp_path: Path) -> None:
    project = tmp_path / "AIP"
    payload = tmp_path / "payload"
    _write(project / "src/aip/original.py", "ORIGINAL\n")
    _write(payload / "src/aip/certified.py", "CERTIFIED_V1\n")

    _replace_src_transactionally(payload, project)
    assert (project / "src/aip/certified.py").read_text(encoding="utf-8") == "CERTIFIED_V1\n"

    _write(payload / "src/aip/certified.py", "CERTIFIED_V2\n")
    _write(payload / "src/aip/second.py", "SECOND\n")
    _replace_src_transactionally(payload, project)

    assert (project / "src/aip/certified.py").read_text(encoding="utf-8") == "CERTIFIED_V2\n"
    assert (project / "src/aip/second.py").read_text(encoding="utf-8") == "SECOND\n"
    assert not (project / ".aip_src_before_certified").exists()
