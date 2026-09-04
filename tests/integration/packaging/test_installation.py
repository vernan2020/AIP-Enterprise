from __future__ import annotations

import os
import site
import subprocess
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _create_venv(path: Path) -> Path:
    # The runner has already installed and validated project dependencies.
    # Reuse them here so these tests exercise AIP packaging rather than
    # downloading the full Qt runtime once per test.
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(path)
    if os.name == "nt":
        return path / "Scripts" / "python.exe"
    return path / "bin" / "python"


def _installed_runtime_environment() -> dict[str, str]:
    """Expose the runner's preinstalled dependencies to the nested packaging venv."""
    environment = dict(os.environ)
    inherited_paths = [path for path in site.getsitepackages() if Path(path).is_dir()]
    existing = environment.get("PYTHONPATH")
    if existing:
        inherited_paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(inherited_paths)
    return environment


def test_editable_install_imports_without_repo_path(tmp_path: Path) -> None:
    venv_path = tmp_path / "venv"
    python_exe = _create_venv(venv_path)
    install = subprocess.run(
        [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-build-isolation",
            "-e",
            str(ROOT),
        ],
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
        [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-build-isolation",
            "-e",
            str(ROOT),
        ],
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
        env=_installed_runtime_environment(),
    )
    assert entrypoint.returncode == 0
