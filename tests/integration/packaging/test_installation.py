from __future__ import annotations

import os
import subprocess
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _create_venv(path: Path) -> Path:
    venv.EnvBuilder(with_pip=True).create(path)
    if os.name == "nt":
        return path / "Scripts" / "python.exe"
    return path / "bin" / "python"


def test_editable_install_imports_without_repo_path(tmp_path: Path) -> None:
    venv_path = tmp_path / "venv"
    python_exe = _create_venv(venv_path)
    install = subprocess.run(
        [str(python_exe), "-m", "pip", "install", "-e", str(ROOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert install.returncode == 0

    import_check = subprocess.run(
        [str(python_exe), "-c", "import aip; print(aip.__version__)"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert import_check.stdout.strip() == "1.0.0-rc1"


def test_console_entry_point_is_available_after_install(tmp_path: Path) -> None:
    venv_path = tmp_path / "venv"
    python_exe = _create_venv(venv_path)
    subprocess.run(
        [str(python_exe), "-m", "pip", "install", "-e", str(ROOT)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    entrypoint = subprocess.run(
        [str(venv_path / ("Scripts" if os.name == "nt" else "bin") / "aip-enterprise"), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert entrypoint.returncode == 0
