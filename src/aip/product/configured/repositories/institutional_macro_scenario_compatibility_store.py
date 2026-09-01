from __future__ import annotations

from collections.abc import Iterable

from aip.product.configured.repositories.institutional_macro_scenario_store import (
    InstitutionalMacroScenarioStore as _InstitutionalMacroScenarioStore,
)


class InstitutionalMacroScenarioStore(_InstitutionalMacroScenarioStore):
    """Scenario store with an idempotent migration for persisted legacy schemas.

    Production installations can contain the institutional macro scenario table
    created by the pre-recovery runtime.  That schema persisted the immutable
    scenario document under a legacy JSON column name.  The recovered runtime
    reads ``scenario_payload_json``.  This adapter upgrades only the column
    contract in place and preserves every existing scenario/version/status row.
    """

    _PAYLOAD_COLUMN = "scenario_payload_json"
    _LEGACY_PAYLOAD_COLUMNS = (
        "scenario_json",
        "payload_json",
        "scenario_payload",
        "scenario_data_json",
        "payload",
    )

    def _create_schema(self) -> None:
        self._migrate_legacy_payload_column_if_required()
        super()._create_schema()

    def _migrate_legacy_payload_column_if_required(self) -> None:
        connection = self._database.connection
        rows = connection.execute(
            "PRAGMA table_info('institutional_macro_scenarios')"
        ).fetchall()
        if not rows:
            return

        columns = tuple(str(row[1]) for row in rows)
        column_lookup = {column.lower(): column for column in columns}
        if self._PAYLOAD_COLUMN in column_lookup:
            return

        source_column = self._resolve_legacy_payload_column(
            columns=columns,
            column_lookup=column_lookup,
        )
        if source_column is None:
            available = ", ".join(columns)
            raise RuntimeError(
                "Cannot migrate institutional_macro_scenarios: "
                "the persisted scenario payload column is unknown. "
                f"Available columns: {available}"
            )

        quoted_source = source_column.replace('"', '""')
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute(
                "ALTER TABLE institutional_macro_scenarios "
                f"ADD COLUMN {self._PAYLOAD_COLUMN} VARCHAR"
            )
            connection.execute(
                "UPDATE institutional_macro_scenarios "
                f"SET {self._PAYLOAD_COLUMN} = \"{quoted_source}\" "
                f"WHERE {self._PAYLOAD_COLUMN} IS NULL"
            )
            missing = int(
                connection.execute(
                    "SELECT COUNT(*) FROM institutional_macro_scenarios "
                    f"WHERE {self._PAYLOAD_COLUMN} IS NULL"
                ).fetchone()[0]
            )
            if missing:
                raise RuntimeError(
                    "Legacy institutional macro scenario migration left "
                    f"{missing} row(s) without a payload"
                )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    @classmethod
    def _resolve_legacy_payload_column(
        cls,
        *,
        columns: Iterable[str],
        column_lookup: dict[str, str],
    ) -> str | None:
        for candidate in cls._LEGACY_PAYLOAD_COLUMNS:
            resolved = column_lookup.get(candidate)
            if resolved is not None:
                return resolved

        for column in columns:
            normalized = column.lower()
            if "json" in normalized and (
                "scenario" in normalized or "payload" in normalized
            ):
                return column
        return None
