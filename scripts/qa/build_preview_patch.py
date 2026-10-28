"""Create a deterministic, source-backed, preview-only update archive.

Run on a verified GitHub Actions checkout. Never packages private files, DuckDB,
environments, fonts, or the certified runtime. Installation is a separate step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT_FILES = frozenset(
    {
        "main.py",
        "pyproject.toml",
        "run_aip_configured.cmd",
        "run_aip_ux_preview.cmd",
        "DIAGNOSTICAR_BCCR_SUGEF.cmd",
        "DIAGNOSTICAR_BCCR_V2.cmd",
        "DIAGNOSTICAR_RTILB_XML.cmd",
        "DIAGNOSTICAR_LIQUIDEZ_SUGEF210_XML_INVERSIONES.cmd",
        "DIAGNOSTICAR_LIQUIDEZ_SUGEF210_PLAN.cmd",
        "DIAGNOSTICAR_LIQUIDEZ_SUGEF210_FLUJO.cmd",
        "VERIFICAR_LIQUIDEZ_SUGEF210_OPERATIVO.cmd",
        "INICIAR_AIP_LIQUIDEZ_SUGEF210.cmd",
        "AUDITAR_FUENTES_CONFIGURADAS.cmd",
        "INSPECCIONAR_HISTORICOS_PREVIEW.cmd",
    }
)
PRIVATE_NAMES = frozenset(
    {
        ".env",
        ".venv",
        ".git",
        "database",
        "runtime.local.cmd",
        "runtime.local.env",
        "__pycache__",
        ".env.local",
    }
)
EXCLUDED_EXTENSIONS = frozenset(
    {".ttf", ".otf", ".woff", ".woff2", ".pyc", ".pyo", ".db", ".duckdb", ".wal"}
)
INSTALLER_FILES = (
    "scripts/qa/apply_preview_patch.py",
    "scripts/qa/preview_patch_installer.cmd",
)


def allowed(path: str) -> bool:
    """Whitelist deployable tracked sources and reject sensitive/path traversal."""
    normalized = PurePosixPath(path)
    parts = normalized.parts
    if (
        not parts
        or path.startswith("/")
        or "\\" in path
        or ".." in parts
        or any(part.lower() in PRIVATE_NAMES for part in parts)
        or normalized.suffix.lower() in EXCLUDED_EXTENSIONS
    ):
        return False
    return (parts[0] in ("src", "scripts") and len(parts) > 1) or path in ROOT_FILES


def tracked_payload_files(root: Path) -> tuple[Path, ...]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--", "src", "scripts", *sorted(ROOT_FILES)],
        cwd=root,
        capture_output=True,
        check=True,
    )
    candidates = [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]
    included: list[Path] = []
    for name in sorted(candidates):
        if not allowed(name):
            continue
        source = root / name
        if source.is_symlink():
            raise ValueError(f"symlink in deployment scope: {name}")
        if not source.is_file():
            raise ValueError(f"tracked file missing: {name}")
        included.append(source)
    if not included or not any(
        str(path.relative_to(root)).startswith("src/aip/") for path in included
    ):
        raise ValueError("AIP source tree is missing")
    return tuple(included)


def _write(archive: zipfile.ZipFile, path: str, data: bytes) -> None:
    member = zipfile.ZipInfo(path, date_time=(2026, 10, 14, 0, 0, 0))
    member.compress_type = zipfile.ZIP_DEFLATED
    member.external_attr = 0o100644 << 16
    archive.writestr(member, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=8)


def build(root: Path, destination: Path) -> dict[str, object]:
    root = root.resolve()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    files = tracked_payload_files(root)
    if not all((root / name).is_file() for name in INSTALLER_FILES):
        raise ValueError("installer resources missing")
    manifest: dict[str, object] = {
        "format": "aip-v451-preview-patch-v1",
        "repository": "vernan2020/AIP-Enterprise",
        "source_sha": sha,
        "target_name": "AIP-V451-PREVIEW",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "files": [],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", allowZip64=True) as archive:
        for file in files:
            name = file.relative_to(root).as_posix()
            data = file.read_bytes()
            manifest["files"].append(
                {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            )
            _write(archive, f"payload/{name}", data)
        _write(archive, "tools/apply_preview_patch.py", (root / INSTALLER_FILES[0]).read_bytes())
        _write(archive, "INSTALAR_PREVIEW.cmd", (root / INSTALLER_FILES[1]).read_bytes())
        _write(
            archive,
            "manifest.json",
            (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
        )
        _write(
            archive,
            "LEEME.txt",
            (
                "AIP ENTERPRISE 4.5.1 - PARCHE SOLO PREVIEW\r\n"
                f"HEAD: {sha}\r\n"
                "Cierre AIP PREVIEW, extraiga este ZIP a una carpeta temporal y "
                "ejecute INSTALAR_PREVIEW.cmd.\r\n"
                "El instalador verifica SHA-256, crea respaldo y nunca toca la "
                "release certificada, .venv, DuckDB o credenciales.\r\n"
                "Para solo verificar: INSTALAR_PREVIEW.cmd --dry-run\r\n"
            ).encode("utf-8"),
        )
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        f"{digest}  {destination.name}\n", encoding="ascii"
    )
    return {"sha": sha, "files": len(files), "sha256": digest, "bytes": destination.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(build(root, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
