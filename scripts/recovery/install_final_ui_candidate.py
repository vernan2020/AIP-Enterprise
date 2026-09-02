from __future__ import annotations

import compileall
import os
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path, PurePosixPath


REPOSITORY = "vernan2020/AIP-Enterprise"
SOURCE_COMMIT = "cdde4045dd28bb8a7d779cce5f6dfac68d12ab38"
ARCHIVE_URL = f"https://codeload.github.com/{REPOSITORY}/tar.gz/{SOURCE_COMMIT}"
USER_AGENT = "AIP-Enterprise-Final-UI/1.2"
TLS_CIPHERS = "DEFAULT:@SECLEVEL=1"

CRITICAL_FILES = (
    "ui/shell/main_window.py",
    "ui/services/theme_service.py",
    "ui/assets/coopealianza_logo.py",
    "ui/themes/palette.py",
    "ui/modules/executive/views/executive_workspace.py",
    "ui/modules/portfolio/views/portfolio_view.py",
    "ui/modules/market/views/market_view.py",
    "ui/modules/price_risk/views/price_risk_view.py",
    "ui/modules/macro_intelligence/views/macro_intelligence_workspace.py",
    "ui/modules/liquidity/views/liquidity_view.py",
    "ui/modules/treasury/views/treasury_view.py",
    "product/configured/repositories/institutional_macro_scenario_compatibility_store.py",
)


def _tls_context() -> ssl.SSLContext:
    """Return a verified TLS context compatible with the corporate CA chain."""

    context = ssl.create_default_context()
    context.set_ciphers(TLS_CIPHERS)
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise RuntimeError("El contexto TLS perdió la validación de certificado")
    return context


def _project_root() -> Path:
    root = Path.cwd().resolve()
    if not (root / "src" / "aip").is_dir():
        raise RuntimeError(
            "Ejecute este instalador desde la raíz de AIP Enterprise; "
            f"no se encontró src\\aip en {root}"
        )
    return root


def _download_archive(destination: Path) -> None:
    request = urllib.request.Request(
        ARCHIVE_URL,
        headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"},
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=120,
            context=_tls_context(),
        ) as response:
            with destination.open("wb") as handle:
                shutil.copyfileobj(response, handle)
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "No se pudo descargar el candidato visual desde GitHub con TLS "
            "verificado compatible con la CA corporativa. "
            f"Detalle: {exc}"
        ) from exc


def _candidate_source_prefixes(members: list[tarfile.TarInfo]) -> tuple[str, ...]:
    """Return every archive prefix that exposes a ``src/aip`` package.

    The repository still contains an old nested ``AIP-Enterprise/src/aip`` tree
    in addition to the authoritative root ``src/aip`` runtime.  Selecting the
    first ``__init__.py`` therefore restores only the small legacy tree.  We
    enumerate all candidates and let the extractor select the complete runtime.
    """

    marker = "/src/aip/"
    prefixes: set[str] = set()
    for member in members:
        if not member.isfile() or not member.name.endswith("/src/aip/__init__.py"):
            continue
        root_prefix = member.name.split(marker, 1)[0]
        prefixes.add(f"{root_prefix}/src/aip/")
    return tuple(sorted(prefixes))


def _candidate_file_count(
    members: list[tarfile.TarInfo],
    source_prefix: str,
) -> int:
    return sum(
        1
        for member in members
        if member.isfile() and member.name.startswith(source_prefix)
    )


def _candidate_contains_critical_files(
    names: set[str],
    source_prefix: str,
) -> bool:
    return all(f"{source_prefix}{relative}" in names for relative in CRITICAL_FILES)


def _select_authoritative_source_prefix(
    members: list[tarfile.TarInfo],
) -> tuple[str, int]:
    candidates = _candidate_source_prefixes(members)
    if not candidates:
        raise RuntimeError("El paquete descargado no contiene ningún src/aip/__init__.py")

    names = {member.name for member in members if member.isfile()}
    ranked: list[tuple[bool, int, int, str]] = []
    for prefix in candidates:
        count = _candidate_file_count(members, prefix)
        has_critical = _candidate_contains_critical_files(names, prefix)
        # Prefer a candidate that contains every critical runtime component;
        # then prefer the largest tree; finally prefer the shallower archive path.
        depth = len(PurePosixPath(prefix).parts)
        ranked.append((has_critical, count, -depth, prefix))

    ranked.sort(reverse=True)
    has_critical, count, _negative_depth, prefix = ranked[0]
    diagnostics = ", ".join(
        f"{item[3]}={item[1]} archivos{' + críticos' if item[0] else ''}"
        for item in ranked
    )
    print(f"      Árboles src/aip detectados: {diagnostics}")

    if not has_critical:
        raise RuntimeError(
            "Ningún árbol src/aip del paquete contiene todos los componentes "
            "críticos del candidato visual"
        )
    return prefix, count


def _extract_aip_source(archive: Path, staging_src: Path) -> Path:
    staging_aip = staging_src / "aip"
    staging_aip.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        source_prefix, expected_files = _select_authoritative_source_prefix(members)

        extracted = 0
        for member in members:
            if not member.name.startswith(source_prefix):
                continue
            if member.isdir():
                continue
            if not member.isfile():
                raise RuntimeError(
                    f"Tipo de archivo no permitido en el paquete: {member.name}"
                )

            relative_text = member.name[len(source_prefix) :]
            relative = PurePosixPath(relative_text)
            if not relative_text or relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError(f"Ruta insegura en el paquete: {member.name}")

            destination = staging_aip.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise RuntimeError(f"No se pudo leer {member.name}")
            with source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            extracted += 1

    if extracted != expected_files:
        raise RuntimeError(
            "Extracción inconsistente: "
            f"se esperaban {expected_files} archivos y se recuperaron {extracted}"
        )
    if extracted < 100:
        raise RuntimeError(
            f"Extracción incompleta: sólo se recuperaron {extracted} archivos"
        )
    print(f"      Árbol autoritativo: {source_prefix} ({extracted} archivos)")
    return staging_aip


def _verify_files(aip_root: Path) -> None:
    missing = [relative for relative in CRITICAL_FILES if not (aip_root / relative).is_file()]
    if missing:
        raise RuntimeError(
            "La versión descargada no contiene todos los componentes críticos: "
            + ", ".join(missing)
        )


def _compile_source(aip_root: Path) -> None:
    if not compileall.compile_dir(str(aip_root), quiet=1, force=True):
        raise RuntimeError("La compilación del candidato visual falló")


def _smoke(root: Path, source_root: Path, *, label: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source_root)
    env["QT_QPA_PLATFORM"] = "offscreen"
    code = r'''
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from aip.ui.services.theme_service import ThemeService
from aip.ui.shell.main_window import MainWindow
from aip.ui.modules.executive.views.executive_workspace import ExecutiveWorkspace
from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView
from aip.ui.modules.market.views.market_view import MarketView
from aip.ui.modules.price_risk.views.price_risk_view import PriceRiskView
from aip.ui.modules.macro_intelligence.views.macro_intelligence_workspace import MacroIntelligenceWorkspace
from aip.ui.modules.liquidity.views.liquidity_view import LiquidityView
from aip.ui.modules.treasury.views.treasury_view import TreasuryView
app = QApplication.instance() or QApplication([])
root = QWidget()
layout = QVBoxLayout(root)
header = QFrame(root)
header.setObjectName("institutionalHeader")
header.setLayout(QHBoxLayout())
layout.addWidget(header)
service = ThemeService()
service.apply(root)
service.apply(root)
logos = header.findChildren(QLabel, "coopealianzaHeaderLogo")
assert len(logos) == 1
assert logos[0].pixmap() is not None and not logos[0].pixmap().isNull()
print("UI IMPORT/BRAND SMOKE PASS")
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(root),
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stdout + "\n" + completed.stderr).strip()
        raise RuntimeError(f"{label} falló:\n{detail}")
    print(completed.stdout.strip())


def main() -> int:
    root = _project_root()
    current_aip = root / "src" / "aip"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = root / "recovery" / "backups" / f"final-ui-{timestamp}"
    backup_aip = backup_dir / "aip"

    print("=" * 80)
    print("AIP ENTERPRISE 2.0 - ACTUALIZACIÓN VISUAL FINAL")
    print("=" * 80)
    print(f"Proyecto: {root}")
    print(f"Commit fuente: {SOURCE_COMMIT}")
    print("TLS: verificación ON · compatibilidad corporativa OpenSSL SECLEVEL=1")
    print("Alcance: src/aip únicamente; no modifica bases ni archivos institucionales")

    with tempfile.TemporaryDirectory(prefix="aip-final-ui-") as temporary:
        temporary_root = Path(temporary)
        archive = temporary_root / "source.tar.gz"
        staging_src = temporary_root / "src"

        print("[1/6] Descargando fuente inmutable...")
        _download_archive(archive)
        print(f"      Descarga: {archive.stat().st_size:,} bytes")

        print("[2/6] Detectando y extrayendo src/aip autoritativo...")
        staging_aip = _extract_aip_source(archive, staging_src)
        _verify_files(staging_aip)

        print("[3/6] Compilando candidato...")
        _compile_source(staging_aip)

        print("[4/6] Ejecutando smoke offscreen previo...")
        _smoke(root, staging_src, label="Smoke previo")

        print("[5/6] Instalando de forma atómica...")
        backup_dir.mkdir(parents=True, exist_ok=False)
        installed = False
        try:
            os.replace(current_aip, backup_aip)
            os.replace(staging_aip, current_aip)
            installed = True

            print("[6/6] Validando instalación local...")
            _verify_files(current_aip)
            _compile_source(current_aip)
            _smoke(root, root / "src", label="Smoke posterior")
        except Exception:
            if installed and current_aip.exists():
                shutil.rmtree(current_aip, ignore_errors=True)
            if backup_aip.exists() and not current_aip.exists():
                os.replace(backup_aip, current_aip)
                print("ROLLBACK: src/aip anterior restaurado correctamente")
            raise

    print()
    print("FINAL UI CANDIDATE INSTALLATION: PASS")
    print(f"Fuente instalada: {SOURCE_COMMIT}")
    print(f"Respaldo local: {backup_dir}")
    print("Logo Coopealianza: PASS")
    print("Módulos visuales críticos: PASS")
    print()
    print("Para abrir AIP: run_aip_configured.cmd")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
