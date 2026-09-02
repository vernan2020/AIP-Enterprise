from __future__ import annotations

import argparse
import compileall
import json
import shutil
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = "vernan2020/AIP-Enterprise"
USER_AGENT = "AIP-Enterprise-Visual-Recovery/2.0"
UI_PREFIX = "src/aip/ui/"
SUPPORT_FILES = {
    "src/aip/product/configured/services/configured_portfolio_dashboard_analytics_service.py",
}


def _request_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _request_json(url: str) -> dict[str, object]:
    return json.loads(_request_bytes(url).decode("utf-8"))


def _validate_commit(commit: str) -> tuple[str, str]:
    normalized = commit.strip().lower()
    if len(normalized) != 40 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise RuntimeError("El commit visual debe ser un SHA Git completo de 40 caracteres")
    encoded = urllib.parse.quote(normalized, safe="")
    payload = _request_json(
        f"https://api.github.com/repos/{REPOSITORY}/commits/{encoded}"
    )
    resolved = str(payload.get("sha") or "").lower()
    if resolved != normalized:
        raise RuntimeError(
            f"GitHub resolvió un commit distinto: solicitado={normalized}, resuelto={resolved}"
        )
    commit_data = payload.get("commit")
    if not isinstance(commit_data, dict):
        raise RuntimeError("GitHub no devolvió metadatos del commit visual")
    tree_data = commit_data.get("tree")
    if not isinstance(tree_data, dict):
        raise RuntimeError("GitHub no devolvió el árbol del commit visual")
    tree_sha = str(tree_data.get("sha") or "")
    if len(tree_sha) != 40:
        raise RuntimeError("SHA del árbol visual inválido")
    return normalized, tree_sha


def _visual_paths(tree_sha: str) -> tuple[str, ...]:
    payload = _request_json(
        f"https://api.github.com/repos/{REPOSITORY}/git/trees/{tree_sha}?recursive=1"
    )
    if bool(payload.get("truncated")):
        raise RuntimeError("El árbol GitHub está truncado; se cancela la instalación visual")
    raw_tree = payload.get("tree")
    if not isinstance(raw_tree, list):
        raise RuntimeError("GitHub no devolvió el contenido del árbol visual")

    paths: list[str] = []
    for item in raw_tree:
        if not isinstance(item, dict) or item.get("type") != "blob":
            continue
        path = str(item.get("path") or "")
        if path.startswith(UI_PREFIX) or path in SUPPORT_FILES:
            paths.append(path)

    if not paths:
        raise RuntimeError("No se encontraron archivos de la capa visual AIP")
    required = {
        "src/aip/ui/shell/main_window.py",
        "src/aip/ui/shell/ribbon.py",
        "src/aip/ui/themes/light_theme.py",
        "src/aip/ui/assets/coopealianza_logo.py",
    }
    missing = sorted(required.difference(paths))
    if missing:
        raise RuntimeError(f"El candidato visual está incompleto: {missing}")
    return tuple(sorted(paths))


def _raw_url(commit: str, path: str) -> str:
    quoted_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{quoted_path}"


def _backup(project_root: Path, paths: tuple[str, ...]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = project_root / ".recovery" / "ui-visual-backups" / timestamp
    copied = 0
    for relative in paths:
        source = project_root / Path(relative)
        if not source.is_file():
            continue
        destination = backup_root / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1
    print(f"Backup visual: {backup_root} ({copied} archivos existentes)")
    return backup_root


def _stage(project_root: Path, commit: str, paths: tuple[str, ...]) -> Path:
    stage_root = Path(tempfile.mkdtemp(prefix="aip-visual-", dir=project_root / ".recovery"))
    for index, relative in enumerate(paths, start=1):
        destination = stage_root / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_request_bytes(_raw_url(commit, relative)))
        if index % 25 == 0 or index == len(paths):
            print(f"Descarga visual: {index}/{len(paths)}")
    if not compileall.compile_dir(str(stage_root / "src"), quiet=1, force=True):
        raise RuntimeError("La capa visual descargada no supera compilación Python")
    return stage_root


def _install(project_root: Path, stage_root: Path, paths: tuple[str, ...]) -> None:
    for relative in paths:
        source = stage_root / Path(relative)
        destination = project_root / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Instala la capa visual AIP Enterprise 2.0 sobre un runtime certificado."
    )
    parser.add_argument("--commit", required=True, help="SHA inmutable del candidato visual")
    parser.add_argument(
        "--project-root",
        default=None,
        help="Raíz del proyecto; por defecto se infiere desde scripts/recovery.",
    )
    args = parser.parse_args()

    project_root = (
        Path(args.project_root).resolve()
        if args.project_root
        else Path(__file__).resolve().parents[2]
    )
    if not (project_root / "src" / "aip").is_dir():
        raise RuntimeError(f"No parece una instalación AIP válida: {project_root}")

    (project_root / ".recovery").mkdir(parents=True, exist_ok=True)
    commit, tree_sha = _validate_commit(args.commit)
    paths = _visual_paths(tree_sha)

    print("=" * 80)
    print("AIP ENTERPRISE 2.0 - INSTALACIÓN DE CAPA VISUAL")
    print("=" * 80)
    print(f"Proyecto: {project_root}")
    print(f"Commit visual: {commit}")
    print(f"Archivos visuales: {len(paths)}")

    _backup(project_root, paths)
    stage_root = _stage(project_root, commit, paths)
    try:
        _install(project_root, stage_root, paths)
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)

    print("Compilación final de src/aip/ui...")
    if not compileall.compile_dir(str(project_root / "src" / "aip" / "ui"), quiet=1, force=True):
        raise RuntimeError("La capa visual instalada no supera compilación final")

    print("CAPA VISUAL AIP ENTERPRISE 2.0: INSTALADA")
    print("La base de datos, fuentes configuradas y cálculos financieros no fueron modificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
