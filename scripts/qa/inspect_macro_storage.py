"""Read-only diagnosis of macro data continuity across AIP installations.

Never writes to, migrates or opens an institutional DuckDB in read/write mode.
Use this to distinguish an empty portable preview from a UI regression.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass(frozen=True)
class MacroDataState:
    path: Path
    exists: bool
    observations: int | None = None
    scenarios: int | None = None
    approved: int | None = None
    error: str | None = None


def inspect_database(path: Path) -> MacroDataState:
    """Check persistence tables without exposing any financial records."""
    path = path.resolve()
    if not path.is_file():
        return MacroDataState(path=path, exists=False)
    try:
        connection = duckdb.connect(str(path), read_only=True)
        try:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main'"
                ).fetchall()
            }
            observations = (
                int(connection.execute("SELECT count(*) FROM economic_history_observations")
                    .fetchone()[0])
                if "economic_history_observations" in table_names
                else 0
            )
            scenarios = (
                int(connection.execute("SELECT count(*) FROM institutional_macro_scenarios")
                    .fetchone()[0])
                if "institutional_macro_scenarios" in table_names
                else 0
            )
            approved = (
                int(
                    connection.execute(
                        "SELECT count(*) FROM institutional_macro_scenarios "
                        "WHERE upper(status) = 'APPROVED'"
                    ).fetchone()[0]
                )
                if "institutional_macro_scenarios" in table_names
                else 0
            )
            return MacroDataState(
                path=path, exists=True, observations=observations,
                scenarios=scenarios, approved=approved,
            )
        finally:
            connection.close()
    except Exception as exc:
        # Never disclose raw exception messages: they can contain private paths.
        return MacroDataState(path=path, exists=True, error=type(exc).__name__)


def _report(name: str, state: MacroDataState) -> None:
    print(f"{name}: {state.path}")
    if not state.exists:
        print("  Archivo: NO EXISTE")
    elif state.error:
        print(f"  Archivo: presente; lectura no disponible ({state.error})")
        print("  Cierre AIP en ambas carpetas antes de reintentar.")
    else:
        print(
            f"  Histórico: {state.observations} observaciones; "
            f"Escenarios: {state.scenarios}; Aprobados: {state.approved}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparar datos macro sin modificarlos")
    parser.add_argument("--anterior", type=Path, required=True,
                        help="Carpeta raíz de la instalación anterior")
    parser.add_argument(
        "--actual", type=Path, default=Path(__file__).resolve().parents[2],
        help="Carpeta raíz de la vista previa V4.5.1",
    )
    args = parser.parse_args()
    previous = inspect_database(args.anterior / "database" / "aip.duckdb")
    current = inspect_database(args.actual / "database" / "aip.duckdb")
    _report("ANTERIOR", previous)
    _report("V4.5.1", current)
    if previous.error or current.error:
        return 2
    if not previous.exists:
        print("No se encontró la base anterior. Revisar otras instalaciones; sin cambios.")
        return 2
    if (previous.observations or 0) > 0 and not (current.observations or 0):
        print("DIFERENCIA: el histórico macro existe solo en la instalación anterior.")
        print("No se copia automáticamente: preservar y respaldar ambas bases.")
    if (previous.approved or 0) > 0 and not (current.approved or 0):
        print("DIFERENCIA: faltan escenarios institucionales aprobados en V4.5.1.")
    if previous.observations == current.observations and previous.approved == current.approved:
        print("Conteos coincidentes; revisar la carga de datos y el estado de los workers Qt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
