from __future__ import annotations

import argparse
import compileall
import datetime as dt
import io
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPOSITORY = "vernan2020/AIP-Enterprise"
TARGET_SHA = "290b4e4438a21114c0df827aa97e6709b79f750c"
USER_AGENT = "AIP-Enterprise-Validated-Snapshot/1.0"
ARCHIVE_URL = f"https://codeload.github.com/{REPOSITORY}/zip/{TARGET_SHA}"

CRITICAL_MEMBERS = (
    Path("src/aip/ui/application/main.py"),
    Path("src/aip/product/configured/readers/sugef_liquidity_indicator_reader.py"),
    Path("src/aip/product/configured/readers/sugef_credit_quality_reader.py"),
    Path("src/aip/product/configured/services/configured_financial_analysis_service.py"),
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runtime_env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["AIP_EXECUTION_MODE"] = "CONFIGURED"
    env["AIP_DEMO_MODE_ENABLED"] = "false"
    env["PYTHONPATH"] = str(root / "src")
    env.setdefault("AIP_FOLDERWATCH_ENABLED", "true")
    env.setdefault("AIP_VECTOR_ENABLED", "true")
    env.setdefault("AIP_BCCR_ENABLED", "true")
    env.setdefault("AIP_BCCR_BASE_URL", "https://apim.bccr.fi.cr")
    env.setdefault("AIP_ALLOW_PRIOR_SOURCE_DATE", "true")
    return env


def _is_certificate_error(exc: Exception) -> bool:
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    return isinstance(reason, ssl.SSLCertVerificationError) or (
        "CERTIFICATE_VERIFY_FAILED" in str(reason)
    )


def _download_with_curl(url: str) -> bytes:
    curl = shutil.which("curl.exe")
    if curl is None:
        raise RuntimeError(
            "Python rechazó el certificado de red y curl.exe no está disponible."
        )
    completed = subprocess.run(
        [
            curl,
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--retry",
            "3",
            "--connect-timeout",
            "20",
            "--max-time",
            "180",
            "--ssl-no-revoke",
            "--header",
            f"User-Agent: {USER_AGENT}",
            "--header",
            "Cache-Control: no-cache",
            url,
        ],
        check=False,
        capture_output=True,
        timeout=210,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"curl.exe no pudo descargar el snapshot (código {completed.returncode}): {detail}"
        )
    if not completed.stdout:
        raise RuntimeError("GitHub devolvió un snapshot vacío.")
    return completed.stdout


def _download_archive() -> bytes:
    print(f"[1/7] Descargando snapshot validado {TARGET_SHA}...")
    request = urllib.request.Request(
        ARCHIVE_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
        },
    )
    last_error: Exception | None = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
            if len(payload) < 10_000:
                raise RuntimeError(
                    f"Snapshot GitHub inesperadamente pequeño: {len(payload)} bytes."
                )
            return payload
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_error = exc
    if os.name == "nt" and last_error is not None and _is_certificate_error(last_error):
        print(
            "      Python no aceptó el certificado institucional; "
            "reintentando con el almacén de certificados de Windows..."
        )
        return _download_with_curl(ARCHIVE_URL)
    raise RuntimeError(f"No fue posible descargar el snapshot: {last_error}")


def _extract_snapshot(payload: bytes, work: Path) -> Path:
    print("[2/7] Verificando y extrayendo snapshot...")
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        members = archive.namelist()
        roots = sorted(
            {
                name.split("/", 1)[0]
                for name in members
                if "/" in name and name.split("/", 1)[0]
            }
        )
        if len(roots) != 1:
            raise RuntimeError(f"Estructura ZIP inesperada: {roots[:5]}")
        for name in members:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError(f"Ruta insegura dentro del snapshot: {name}")
        archive.extractall(work)

    extracted = work / roots[0]
    for relative in CRITICAL_MEMBERS:
        if not (extracted / relative).is_file():
            raise RuntimeError(f"Falta módulo crítico en snapshot: {relative}")
    return extracted


def _compile_staged_source(extracted: Path) -> None:
    print("[3/7] Compilando fuente antes de instalar...")
    if not compileall.compile_dir(
        str(extracted / "src"),
        quiet=1,
        force=True,
    ):
        raise RuntimeError("El snapshot contiene errores de compilación Python.")


def _backup_current(root: Path) -> Path:
    print("[4/7] Creando rollback local...")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = root / f"AIP_BEFORE_VALIDATED_SNAPSHOT_{stamp}.zip"
    excluded = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        source = root / "src"
        if source.is_dir():
            for path in source.rglob("*"):
                if not path.is_file():
                    continue
                relative = path.relative_to(root)
                if any(part in excluded for part in relative.parts):
                    continue
                if path.suffix.lower() in {".pyc", ".pyo"}:
                    continue
                archive.write(path, relative.as_posix())
        launcher = root / "run_aip_configured.cmd"
        if launcher.is_file():
            archive.write(launcher, launcher.name)
    print(f"      Rollback: {backup.name}")
    return backup


def _replace_source_transactionally(root: Path, extracted: Path) -> Path:
    print("[5/7] Instalando runtime validado transaccionalmente...")
    current = root / "src"
    staged = root / ".aip_validated_src_staging"
    previous = root / ".aip_validated_src_previous"

    shutil.rmtree(staged, ignore_errors=True)
    shutil.rmtree(previous, ignore_errors=True)
    shutil.copytree(extracted / "src", staged)

    if current.exists():
        os.replace(current, previous)
    try:
        os.replace(staged, current)
    except Exception:
        if previous.exists() and not current.exists():
            os.replace(previous, current)
        raise

    launcher_source = extracted / "run_aip_configured.cmd"
    if launcher_source.is_file():
        shutil.copy2(launcher_source, root / "run_aip_configured.cmd")
    return previous


def _run(root: Path, args: list[str], *, env: dict[str, str]) -> None:
    completed = subprocess.run(args, cwd=root, env=env, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Comando falló con código {completed.returncode}: {' '.join(args)}"
        )


def _validate_installed_runtime(root: Path) -> None:
    print("[6/7] Ejecutando preflight del runtime configurado...")
    env = _runtime_env(root)
    _run(root, [sys.executable, "-m", "compileall", "-q", "src"], env=env)
    _run(root, [sys.executable, "-m", "aip.tools.preflight_runtime"], env=env)

    certifier = root / "scripts" / "recovery" / "certify_installed_runtime.py"
    if certifier.is_file():
        print("      Ejecutando certificación profunda instalada...")
        _run(root, [sys.executable, str(certifier)], env=env)


def install() -> int:
    root = _project_root()
    if not (root / "src" / "aip").is_dir():
        raise RuntimeError(f"No se encontró un runtime AIP en {root}")

    print("=" * 76)
    print("AIP ENTERPRISE - INSTALL VALIDATED BRANCH SNAPSHOT")
    print(f"Project root: {root}")
    print(f"Validated runtime commit: {TARGET_SHA}")
    print("=" * 76)

    payload = _download_archive()
    backup: Path | None = None
    previous: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="aip_validated_snapshot_") as temp_dir:
            extracted = _extract_snapshot(payload, Path(temp_dir))
            _compile_staged_source(extracted)
            backup = _backup_current(root)
            previous = _replace_source_transactionally(root, extracted)

        try:
            _validate_installed_runtime(root)
        except Exception:
            print("      Validación falló; restaurando runtime anterior...")
            current = root / "src"
            if current.exists():
                shutil.rmtree(current, ignore_errors=True)
            if previous is not None and previous.exists():
                os.replace(previous, current)
            raise

        if previous is not None and previous.exists():
            shutil.rmtree(previous, ignore_errors=True)

        print("[7/7] INSTALACIÓN VALIDADA: PASS")
        print(f"      Runtime commit: {TARGET_SHA}")
        if backup is not None:
            print(f"      Rollback retenido: {backup}")
        print("      Inicie AIP con: run_aip_configured.cmd")
        return 0
    finally:
        shutil.rmtree(root / ".aip_validated_src_staging", ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Instala el snapshot AIP RC1 fijado al commit validado por CI, sin Git."
        )
    )


def main(argv: list[str] | None = None) -> int:
    _parser().parse_args(argv)
    try:
        return install()
    except Exception as exc:
        print()
        print(f"INSTALACIÓN VALIDADA: FAILED - {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
