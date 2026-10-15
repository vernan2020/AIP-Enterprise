"""Conservative, opt-in history recovery for the existing configured AIP.

The certified database is attached READ_ONLY. Only official macro observations
and approved-scenario audit tables may be copied to the PREVIEW database, and
only if the destination table is empty. No financial calculations or credentials
are altered. The default operation is inspection, not restoration.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import duckdb

from aip.product.configured.repositories.economic_historical_store import (
    EconomicHistoricalStore,
)
from aip.product.configured.repositories.institutional_macro_scenario_store import (
    InstitutionalMacroScenarioStore,
)

_TABLES = (
    "economic_history_observations",
    "institutional_macro_scenarios",
    "institutional_macro_scenario_reviews",
    "institutional_macro_scenario_events",
)

_CERTIFIED = Path(
    r"C:\Proyectos\AIP-TIR5-RC1\AIP-Enterprise-release-core-v1.0\database\aip.duckdb"
)


def inventory(path: Path) -> dict[str, int | None]:
    """Inspect row counts without initializing schemas or writing to the file."""
    if not path.is_file():
        return {name: None for name in _TABLES}
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()
        }
        return {
            name: (
                int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                if name in tables
                else None
            )
            for name in _TABLES
        }


def _quoted(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def recover(
    source: Path, destination: Path, *, apply: bool = False
) -> tuple[str, ...]:
    """Never overwrite populated tables; back up preview before changes."""
    if not source.is_file() or not destination.is_file():
        raise ValueError("Se requieren ambas bases existentes; no se crean bases nuevas.")
    if source.resolve() == destination.resolve():
        raise ValueError("Origen y destino son la misma base; restauración bloqueada.")
    source_counts = inventory(source)
    destination_counts = inventory(destination)
    notes = [
        "RECUPERACIÓN DE HISTÓRICOS · SIN SUSTITUIR LA BASE CERTIFICADA",
        "Origen certificado: lectura exclusiva; destino: copia PREVIEW.",
    ]
    for name in _TABLES:
        src, dst = source_counts[name], destination_counts[name]
        label = (
            "SIN TABLA EN ORIGEN"
            if src is None or src == 0
            else "DESTINO POBLADO: SE CONSERVA"
            if dst not in {0, None}
            else "RECUPERABLE"
        )
        notes.append(f"{name}: certificado={src}; preview={dst}; {label}")
    if not apply:
        notes.append("SOLO DIAGNÓSTICO. Nada fue modificado.")
        return tuple(notes)
    if not any(
        source_counts[name] and destination_counts[name] in {None, 0}
        for name in _TABLES
    ):
        notes.append("Nada por restaurar: no se realizaron modificaciones.")
        return tuple(notes)
    # Scenario metadata and its review/event trails form one governance unit.
    # Mixing an existing PREVIEW scenario history with certified audit records
    # from another snapshot would make approvals and traceability ambiguous.
    scenario_tables = _TABLES[1:]
    existing_scenario_data = any(
        (destination_counts[name] or 0) > 0 for name in scenario_tables
    )
    missing_certified_scenario_data = any(
        (source_counts[name] or 0) > 0 and not destination_counts[name]
        for name in scenario_tables
    )
    if existing_scenario_data and missing_certified_scenario_data:
        raise ValueError(
            "PREVIEW contiene una parte de los escenarios: "
            "se requiere conciliación antes de restaurar auditoría."
        )

    # The restored schema comes from the existing application repositories.
    # Back up PREVIEW first, before any potentially mutating operation.
    backup_dir = destination.parent / "backups" / datetime.now().strftime(
        "macro-%Y%m%d-%H%M%S-%f"
    )
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup = backup_dir / "aip.duckdb"
    shutil.copy2(destination, backup)
    if backup.stat().st_size != destination.stat().st_size:
        raise RuntimeError("Respaldo de PREVIEW incompleto; abortar.")
    # A leftover DuckDB WAL may contain valid, committed PREVIEW changes.
    # Preserve both files BEFORE opening PREVIEW for any write/checkpoint.
    wal = destination.with_name(destination.name + ".wal")
    if wal.exists():
        wal_copy = backup_dir / wal.name
        shutil.copy2(wal, wal_copy)
        if wal_copy.stat().st_size != wal.stat().st_size:
            raise RuntimeError("Respaldo WAL incompleto; abortar.")
        notes.append("WAL de PREVIEW respaldado junto a la base original.")
    notes.append("Respaldo de PREVIEW creado antes de modificar datos.")
    # The exclusive connection fails safely if AIP is still running.
    # DuckDB checkpoints any valid WAL into PREVIEW (never CERTIFICADA).
    with duckdb.connect(str(destination), read_only=False) as target:
        target.execute("CHECKPOINT")
    if inventory(destination) != destination_counts:
        raise ValueError("PREVIEW cambió durante checkpoint; abortar y revisar respaldo.")

    root = destination.parent.parent
    history_store = EconomicHistoricalStore(project_root=root)
    scenario_store = InstitutionalMacroScenarioStore(project_root=root)
    try:
        history_store.initialize()
    finally:
        history_store.close()
    try:
        scenario_store.initialize()
    finally:
        scenario_store.close()

    with duckdb.connect(str(destination), read_only=False) as target:
        target.execute(f"ATTACH '{_quoted(source)}' AS previous (READ_ONLY)")
        target.execute("BEGIN TRANSACTION")
        try:
            for name in _TABLES:
                if not source_counts[name]:
                    continue
                count = int(target.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                if count:
                    continue
                source_info = target.execute(
                    f"DESCRIBE SELECT * FROM previous.main.{name}"
                ).fetchall()
                dest_info = target.execute(f"DESCRIBE SELECT * FROM main.{name}").fetchall()
                source_schema = tuple((row[0], row[1]) for row in source_info)
                destination_schema = tuple((row[0], row[1]) for row in dest_info)
                if source_schema != destination_schema:
                    raise ValueError(
                        f"Esquema incompatible en {name}; "
                        "no se restauró ninguna tabla."
                    )
                target.execute(
                    f"INSERT INTO main.{name} SELECT * FROM previous.main.{name}"
                )
                copied = int(
                    target.execute(f"SELECT COUNT(*) FROM main.{name}").fetchone()[0]
                )
                if copied != source_counts[name]:
                    raise RuntimeError("La reconciliación de datos restaurados falló.")
                notes.append(f"{name}: restauradas {copied} filas originales.")
            target.execute("COMMIT")
        except Exception:
            target.execute("ROLLBACK")
            raise
        finally:
            target.execute("DETACH previous")
    notes.append("RESTABLECIMIENTO CONFIRMADO SOLO EN PREVIEW.")
    return tuple(notes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recuperar históricos oficiales sin DEMO")
    parser.add_argument("--source", type=Path, default=_CERTIFIED)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path.cwd() / "database" / "aip.duckdb",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        for message in recover(args.source, args.destination, apply=args.apply):
            print(message)
    except (OSError, RuntimeError, ValueError, duckdb.Error):
        print("RECUPERACIÓN DETENIDA: archivo bloqueado, ilegible o incompatible.")
        print("No sustituya manualmente las bases. Cierre AIP antes de reintentar.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
