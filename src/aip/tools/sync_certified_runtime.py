from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
_ARCHIVE_URL = "https://codeload.github.com/vernan2020/AIP-Enterprise/zip/{commit}"


def _validate_commit(value: str) -> str:
    commit = value.strip().lower()
    if not _COMMIT_PATTERN.fullmatch(commit):
        raise argparse.ArgumentTypeError(
            "--commit debe ser un SHA Git completo de 40 caracteres hexadecimales"
        )
    return commit


def _project_root(value: str | None) -> Path:
    root = Path(value).expanduser().resolve() if value else Path.cwd().resolve()
    if not (root / "pyproject.toml").is_file():
        raise ValueError(f"No se encontró pyproject.toml en {root}")
    if not (root / "src" / "aip" / "__init__.py").is_file():
        raise ValueError(f"No se encontró src\\aip en {root}")
    return root


def _local_archive(value: str | None) -> Path | None:
    if value is None:
        return None
    archive = Path(value).expanduser().resolve()
    if not archive.is_file():
        raise ValueError(f"No se encontró el archivo ZIP local: {archive}")
    if not zipfile.is_zipfile(archive):
        raise ValueError(f"El archivo local no es un ZIP válido: {archive}")
    return archive


def _download_archive(commit: str, destination: Path) -> None:
    url = _ARCHIVE_URL.format(commit=commit)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AIP-Enterprise-Runtime-Sync"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310
        if getattr(response, "status", 200) != 200:
            raise RuntimeError(f"GitHub respondió HTTP {response.status}")
        with destination.open("wb") as target:
            shutil.copyfileobj(response, target)


def _extract_aip_tree(archive_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    extracted_root = destination / "aip"
    extracted_root.mkdir(parents=True, exist_ok=True)
    copied = 0

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            member_path = PurePosixPath(member.filename)
            parts = member_path.parts
            try:
                src_index = parts.index("src")
            except ValueError:
                continue
            if len(parts) <= src_index + 1 or parts[src_index + 1] != "aip":
                continue

            relative_parts = parts[src_index + 2 :]
            if not relative_parts:
                continue
            if any(part in {"", ".", ".."} for part in relative_parts):
                raise RuntimeError(f"Ruta insegura en archivo ZIP: {member.filename}")

            target = extracted_root.joinpath(*relative_parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            copied += 1

    if copied == 0 or not (extracted_root / "__init__.py").is_file():
        raise RuntimeError("El ZIP descargado no contiene un runtime AIP válido")
    return extracted_root


def _verify_runtime(project_root: Path) -> None:
    env = os.environ.copy()
    src_path = str(project_root / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_path if not existing else src_path + os.pathsep + existing

    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(project_root / "src" / "aip")],
        cwd=project_root,
        env=env,
        check=False,
    )
    if compile_result.returncode != 0:
        raise RuntimeError("La compilación del runtime sincronizado falló")

    import_result = subprocess.run(
        [sys.executable, "-c", "import aip; print(aip.__file__)"],
        cwd=project_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if import_result.returncode != 0:
        message = import_result.stderr.strip() or "import aip falló"
        raise RuntimeError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sincroniza únicamente src/aip desde un commit certificado de AIP Enterprise, "
            "con respaldo y rollback automático."
        )
    )
    parser.add_argument(
        "--commit",
        required=True,
        type=_validate_commit,
        help="SHA completo certificado",
    )
    parser.add_argument(
        "--archive",
        default=None,
        help=(
            "ZIP local del commit certificado. Si se indica, Python no descarga desde GitHub; "
            "es útil cuando la red corporativa usa un certificado TLS incompatible con OpenSSL."
        ),
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Raíz local del proyecto. Por defecto usa el directorio actual.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida el runtime sin modificar la instalación local.",
    )
    return parser


def _install_runtime(project_root: Path, staged_aip: Path, commit: str) -> Path:
    current = project_root / "src" / "aip"
    backup_root = project_root / "_backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_root / f"aip_{timestamp}_{commit[:12]}"

    if backup.exists():
        raise RuntimeError(f"Ya existe el respaldo {backup}")

    current.rename(backup)
    try:
        shutil.copytree(staged_aip, current)
        _verify_runtime(project_root)
        (project_root / "AIP_SYNC_COMMIT.txt").write_text(commit + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(current, ignore_errors=True)
        backup.rename(current)
        raise
    return backup


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        project_root = _project_root(args.project_root)
        local_archive = _local_archive(args.archive)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    commit: str = args.commit
    print("=== AIP ENTERPRISE · SINCRONIZACIÓN CERTIFICADA ===")
    print(f"Proyecto: {project_root}")
    print(f"Commit objetivo: {commit}")
    print("Alcance: src\\aip únicamente; .venv, datos y configuración local no se modifican.")

    with tempfile.TemporaryDirectory(prefix="aip_certified_sync_") as temp_dir:
        temp = Path(temp_dir)
        downloaded_archive = temp / "runtime.zip"
        stage = temp / "stage"
        try:
            if local_archive is None:
                print("Descargando runtime certificado desde GitHub...")
                _download_archive(commit, downloaded_archive)
                archive = downloaded_archive
            else:
                print(f"Usando ZIP local certificado: {local_archive}")
                archive = local_archive

            staged_aip = _extract_aip_tree(archive, stage)
            if args.dry_run:
                print(
                    "DRY-RUN OK: estructura del runtime válida; "
                    "no se modificó el proyecto."
                )
                return 0

            backup = _install_runtime(project_root, staged_aip, commit)
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}")
            print("La instalación local anterior se mantiene o fue restaurada automáticamente.")
            return 1

    print("SINCRONIZACIÓN OK")
    print(f"Commit instalado: {commit}")
    print(f"Respaldo anterior: {backup}")
    print("Verificación: compileall + import aip = OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
