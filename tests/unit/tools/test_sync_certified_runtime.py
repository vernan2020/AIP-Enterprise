from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import pytest

from aip.tools import sync_certified_runtime as sync

_COMMIT = "a" * 40


def _build_archive(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "AIP-Enterprise-deadbeef/src/aip/__init__.py",
            "VALUE = 'new'\n",
        )
        archive.writestr(
            "AIP-Enterprise-deadbeef/src/aip/module.py",
            "VALUE = 1\n",
        )
        archive.writestr(
            "AIP-Enterprise-deadbeef/tests/ignored.py",
            "SHOULD_NOT_COPY = True\n",
        )


def test_validate_commit_requires_full_sha() -> None:
    assert sync._validate_commit(_COMMIT.upper()) == _COMMIT
    with pytest.raises(argparse.ArgumentTypeError):
        sync._validate_commit("abc123")


def test_local_archive_requires_existing_valid_zip(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    _build_archive(archive)

    assert sync._local_archive(str(archive)) == archive.resolve()
    assert sync._local_archive(None) is None

    with pytest.raises(ValueError, match="No se encontró"):
        sync._local_archive(str(tmp_path / "missing.zip"))

    invalid = tmp_path / "invalid.zip"
    invalid.write_text("not a zip", encoding="utf-8")
    with pytest.raises(ValueError, match="no es un ZIP válido"):
        sync._local_archive(str(invalid))


def test_extract_aip_tree_copies_only_runtime(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    _build_archive(archive)

    extracted = sync._extract_aip_tree(archive, tmp_path / "stage")

    assert (extracted / "__init__.py").read_text(encoding="utf-8") == "VALUE = 'new'\n"
    assert (extracted / "module.py").is_file()
    assert not (tmp_path / "stage" / "tests").exists()


def test_install_runtime_creates_backup_and_commit_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    current = project / "src" / "aip"
    current.mkdir(parents=True)
    (current / "__init__.py").write_text("VALUE = 'old'\n", encoding="utf-8")
    (current / "stale.py").write_text("STALE = True\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname='aip-test'\n",
        encoding="utf-8",
    )
    (project / "local-data.txt").write_text("preserve", encoding="utf-8")

    staged = tmp_path / "staged" / "aip"
    staged.mkdir(parents=True)
    (staged / "__init__.py").write_text("VALUE = 'new'\n", encoding="utf-8")
    (staged / "new.py").write_text("NEW = True\n", encoding="utf-8")
    monkeypatch.setattr(sync, "_verify_runtime", lambda _root: None)

    backup = sync._install_runtime(project, staged, _COMMIT)

    assert (project / "src" / "aip" / "__init__.py").read_text(
        encoding="utf-8"
    ) == "VALUE = 'new'\n"
    assert (project / "src" / "aip" / "new.py").is_file()
    assert not (project / "src" / "aip" / "stale.py").exists()
    assert (backup / "__init__.py").read_text(encoding="utf-8") == "VALUE = 'old'\n"
    assert (backup / "stale.py").is_file()
    assert (project / "AIP_SYNC_COMMIT.txt").read_text(encoding="utf-8") == _COMMIT + "\n"
    assert (project / "local-data.txt").read_text(encoding="utf-8") == "preserve"


def test_install_runtime_does_not_rename_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    current = project / "src" / "aip"
    current.mkdir(parents=True)
    (current / "__init__.py").write_text("VALUE = 'old'\n", encoding="utf-8")

    staged = tmp_path / "staged" / "aip"
    staged.mkdir(parents=True)
    (staged / "__init__.py").write_text("VALUE = 'new'\n", encoding="utf-8")
    monkeypatch.setattr(sync, "_verify_runtime", lambda _root: None)

    def forbidden_rename(self: Path, _target: Path) -> Path:
        raise AssertionError(f"rename no debe utilizarse para {self}")

    monkeypatch.setattr(Path, "rename", forbidden_rename)

    sync._install_runtime(project, staged, _COMMIT)

    assert (current / "__init__.py").read_text(encoding="utf-8") == "VALUE = 'new'\n"


def test_install_runtime_rolls_back_when_verification_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    current = project / "src" / "aip"
    current.mkdir(parents=True)
    (current / "__init__.py").write_text("VALUE = 'old'\n", encoding="utf-8")
    (current / "old_only.py").write_text("OLD = True\n", encoding="utf-8")

    staged = tmp_path / "staged" / "aip"
    staged.mkdir(parents=True)
    (staged / "__init__.py").write_text("VALUE = 'new'\n", encoding="utf-8")
    (staged / "new_only.py").write_text("NEW = True\n", encoding="utf-8")

    def fail_verification(_root: Path) -> None:
        raise RuntimeError("verification failed")

    monkeypatch.setattr(sync, "_verify_runtime", fail_verification)

    with pytest.raises(RuntimeError, match="verification failed"):
        sync._install_runtime(project, staged, _COMMIT)

    assert (project / "src" / "aip" / "__init__.py").read_text(
        encoding="utf-8"
    ) == "VALUE = 'old'\n"
    assert (project / "src" / "aip" / "old_only.py").is_file()
    assert not (project / "src" / "aip" / "new_only.py").exists()
    assert not (project / "AIP_SYNC_COMMIT.txt").exists()
