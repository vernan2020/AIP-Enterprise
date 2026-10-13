"""Read-only comparison of configured data and secret-presence flags across installs.

Run via AUDITAR_FUENTES_CONFIGURADAS.cmd. Never log actual tokens, passwords,
usernames, service URLs, SQL connection strings or contents of source files.
"""

from __future__ import annotations

import os
from pathlib import Path


def _flag(name: str, environment: dict[str, str]) -> str:
    return "PRESENTE" if bool(environment.get(name, "").strip()) else "NO VISIBLE"


def _database_state(base: Path) -> str:
    candidate = base / "database" / "aip.duckdb"
    try:
        if candidate.is_file():
            return f"presente, {candidate.stat().st_size:,} bytes"
    except OSError:
        return "no accesible"
    return "no encontrado"


def audit_source_configuration(
    preview: Path,
    certified: Path,
    environment: dict[str, str],
) -> list[str]:
    """Expose only non-sensitive availability states, never source values."""
    lines = [
        "AUDITORÍA LOCAL SIN MODIFICACIONES · NO MUESTRA CREDENCIALES",
        "La presencia en esta sesión no acredita conectividad con BCCR/SUGEF.",
        f"BCCR token en entorno: {_flag('AIP_BCCR_TOKEN', environment)}",
        f"BCCR nombre en entorno: {_flag('AIP_BCCR_NAME', environment)}",
        f"BCCR correo en entorno: {_flag('AIP_BCCR_EMAIL', environment)}",
        f"Config. privada externa: {_flag('AIP_RUNTIME_LOCAL_CMD', environment)}",
        f"SUGEF raíz local configurada: {_flag('AIP_SUGEF_FINANCIAL_ROOT', environment)}",
        "SUGEF API: "
        + (
            "DESHABILITADA"
            if environment.get("AIP_SUGEF_FINANCIAL_API_ENABLED", "true")
            .strip()
            .lower() in {"false", "0", "no"}
            else "HABILITADA POR CONFIGURACIÓN"
        ),
    ]
    for label, base in (("PREVIEW", preview), ("CERTIFICADA", certified)):
        lines.extend(
            (
                f"{label}: DuckDB {_database_state(base)}",
                f"{label}: runtime.local.cmd "
                + ("presente" if (base / "config" / "runtime.local.cmd").is_file() else "ausente"),
                f"{label}: .env "
                + ("presente" if (base / ".env").is_file() else "ausente"),
            )
        )
    if not (preview / "database" / "aip.duckdb").is_file():
        lines.append("AVISO: PREVIEW no tiene base persistente.")
    lines.append("Diagnóstico de rutas únicamente. No se consultaron APIs ni se copiaron datos.")
    return lines


def main() -> int:
    preview = Path(__file__).resolve().parents[2]
    certified = Path(
        r"C:\Proyectos\AIP-TIR5-RC1\AIP-Enterprise-release-core-v1.0"
    )
    for line in audit_source_configuration(preview, certified, dict(os.environ)):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
