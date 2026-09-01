from __future__ import annotations

import os
import subprocess
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _create_virtualenv(path: Path) -> Path:
    venv.EnvBuilder(with_pip=True).create(path)
    if os.name == "nt":
        return path / "Scripts" / "python.exe"
    return path / "bin" / "python"


def test_package_exports_canonical_version_and_resources() -> None:
    import importlib.resources as resources

    import aip

    assert aip.__version__ == "1.0.0-rc1"
    config_file = resources.files("aip").joinpath("resources/config/application.yaml")
    assert config_file.is_file()


def test_editable_install_supports_import_without_repo_path(tmp_path: Path) -> None:
    env_dir = tmp_path / "venv"
    python_exe = _create_virtualenv(env_dir)

    install = subprocess.run(
        [str(python_exe), "-m", "pip", "install", "-e", str(REPO_ROOT)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0

    import_check = subprocess.run(
        [str(python_exe), "-c", "import aip; print(aip.__version__)"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert import_check.stdout.strip() == "1.0.0-rc1"
