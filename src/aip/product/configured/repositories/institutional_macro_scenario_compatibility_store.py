from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from typing import Any

from aip.product.configured.repositories.institutional_macro_scenario_store import (
    InstitutionalMacroScenarioStore as _InstitutionalMacroScenarioStore,
)
from aip.product.economic.institutional_macro_scenario import (
    InstitutionalMacroScenario,
    InstitutionalMacroScenarioIndicator,
    InstitutionalMacroScenarioPoint,
)


class InstitutionalMacroScenarioStore(_InstitutionalMacroScenarioStore):
    """Scenario store with idempotent migrations for persisted legacy schemas.

    Production installations can contain either a denormalized scenario table
    with the immutable document stored under a legacy JSON column name, or the
    earlier normalized relational layout where metadata, indicators and points
    live in separate tables. Both migrations preserve the original evidence,
    reconstruct the canonical immutable JSON payload and retain workflow audit
    and review history. Unknown layouts fail loudly instead of fabricating
    scenario data.
    """

    _PAYLOAD_COLUMN = "scenario_payload_json"
    _UPDATED_AT_COLUMN = "updated_at"
    _LEGACY_PAYLOAD_COLUMNS = (
        "scenario_json",
        "payload_json",
        "scenario_payload",
        "scenario_data_json",
        "payload",
    )

    _RELATIONAL_INDICATOR_TABLE = "institutional_macro_scenario_indicators"
    _RELATIONAL_POINT_TABLE = "institutional_macro_scenario_points"
    _LEGACY_AUDIT_TABLE = "institutional_macro_scenario_audit"
    _LEGACY_REVIEW_TABLE = "institutional_macro_scenario_review_resolutions"

    _RELATIONAL_PARENT_COLUMNS = frozenset(
        {
            "scenario_id",
            "version",
            "scenario_type",
            "status",
            "dataset_as_of_date",
            "horizon_months",
            "created_at",
            "created_by",
            "description",
        }
    )
    _RELATIONAL_INDICATOR_COLUMNS = frozenset(
        {
            "scenario_id",
            "version",
            "indicator_code",
            "statistical_model_name",
            "statistical_model_family",
            "governance_model_name",
            "governance_model_family",
            "institutional_status",
            "data_as_of_date",
            "forecast_origin_period",
            "last_observed_value",
            "historical_observations",
            "weighted_relative_score",
            "improvement_vs_naive",
            "dynamic_stability_status",
            "dynamic_stability_ratio",
            "data_lag_days",
            "data_lag_months",
            "is_current_period",
            "approved_for_base_scenario",
            "reason_codes",
            "warnings",
            "diagnostic",
        }
    )
    _RELATIONAL_POINT_COLUMNS = frozenset(
        {
            "scenario_id",
            "version",
            "indicator_code",
            "horizon",
            "target_period",
            "point_forecast",
            "lower_bound",
            "upper_bound",
            "confidence_level",
        }
    )

    def _create_schema(self) -> None:
        self._migrate_legacy_payload_column_if_required()
        super()._create_schema()
        self._sync_legacy_workflow_tables_if_present()

    def _migrate_legacy_payload_column_if_required(self) -> None:
        columns = self._table_column_names("institutional_macro_scenarios")
        if not columns:
            return

        column_lookup = {column.lower(): column for column in columns}
        if self._PAYLOAD_COLUMN in column_lookup:
            self._ensure_updated_at_column_if_required(columns)
            return

        source_column = self._resolve_legacy_payload_column(
            columns=columns,
            column_lookup=column_lookup,
        )
        if source_column is not None:
            self._migrate_legacy_json_payload_column(
                source_column=source_column,
                columns=columns,
            )
            return

        if self._is_normalized_relational_schema(columns):
            payloads = self._build_normalized_relational_payloads()
            self._install_reconstructed_payloads(
                payloads=payloads,
                columns=columns,
            )
            return

        available = ", ".join(columns)
        raise RuntimeError(
            "Cannot migrate institutional_macro_scenarios: "
            "the persisted scenario payload column is unknown and the "
            "normalized relational scenario schema is incomplete. "
            f"Available columns: {available}"
        )

    def _migrate_legacy_json_payload_column(
        self,
        *,
        source_column: str,
        columns: Iterable[str],
    ) -> None:
        connection = self._database.connection
        quoted_source = source_column.replace('"', '""')
        column_lookup = {column.lower() for column in columns}
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute(
                "ALTER TABLE institutional_macro_scenarios "
                f"ADD COLUMN {self._PAYLOAD_COLUMN} VARCHAR"
            )
            if self._UPDATED_AT_COLUMN not in column_lookup:
                connection.execute(
                    "ALTER TABLE institutional_macro_scenarios "
                    f"ADD COLUMN {self._UPDATED_AT_COLUMN} TIMESTAMP"
                )
            connection.execute(
                "UPDATE institutional_macro_scenarios "
                f'SET {self._PAYLOAD_COLUMN} = "{quoted_source}" '
                f"WHERE {self._PAYLOAD_COLUMN} IS NULL"
            )
            connection.execute(
                "UPDATE institutional_macro_scenarios "
                f"SET {self._UPDATED_AT_COLUMN} = "
                f"COALESCE({self._UPDATED_AT_COLUMN}, now())"
            )
            self._assert_no_missing_payloads()
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def _is_normalized_relational_schema(
        self,
        parent_columns: Iterable[str],
    ) -> bool:
        parent = {column.lower() for column in parent_columns}
        if not self._RELATIONAL_PARENT_COLUMNS.issubset(parent):
            return False
        indicator_columns = self._table_columns(self._RELATIONAL_INDICATOR_TABLE)
        point_columns = self._table_columns(self._RELATIONAL_POINT_TABLE)
        return self._RELATIONAL_INDICATOR_COLUMNS.issubset(
            indicator_columns
        ) and self._RELATIONAL_POINT_COLUMNS.issubset(point_columns)

    def _build_normalized_relational_payloads(
        self,
    ) -> tuple[tuple[str, int, str], ...]:
        connection = self._database.connection
        parent_rows = connection.execute("""
            SELECT
                scenario_id, version, scenario_type, status,
                dataset_as_of_date, horizon_months, created_at,
                created_by, description
            FROM institutional_macro_scenarios
            ORDER BY scenario_id, version
            """).fetchall()

        payloads: list[tuple[str, int, str]] = []
        for parent in parent_rows:
            scenario_id = str(parent[0])
            version = int(parent[1])
            horizon_months = int(parent[5])
            indicator_rows = connection.execute(
                f"""
                SELECT
                    indicator_code,
                    statistical_model_name,
                    statistical_model_family,
                    governance_model_name,
                    governance_model_family,
                    institutional_status,
                    data_as_of_date,
                    forecast_origin_period,
                    last_observed_value,
                    historical_observations,
                    weighted_relative_score,
                    improvement_vs_naive,
                    dynamic_stability_status,
                    dynamic_stability_ratio,
                    data_lag_days,
                    data_lag_months,
                    is_current_period,
                    approved_for_base_scenario,
                    reason_codes,
                    warnings,
                    diagnostic
                FROM {self._RELATIONAL_INDICATOR_TABLE}
                WHERE scenario_id = ? AND version = ?
                ORDER BY indicator_code
                """,
                [scenario_id, version],
            ).fetchall()
            if not indicator_rows:
                raise RuntimeError(
                    "Normalized institutional macro scenario migration found "
                    f"no indicators for {scenario_id} v{version}"
                )

            seen_codes: set[str] = set()
            indicators: list[InstitutionalMacroScenarioIndicator] = []
            for item in indicator_rows:
                source_indicator_code = str(item[0])
                indicator_code = source_indicator_code.strip().upper()
                if not indicator_code or indicator_code in seen_codes:
                    raise RuntimeError(
                        "Normalized institutional macro scenario migration found "
                        f"a duplicate/empty indicator for {scenario_id} "
                        f"v{version}: {indicator_code!r}"
                    )
                seen_codes.add(indicator_code)

                point_rows = connection.execute(
                    f"""
                    SELECT
                        horizon, target_period, point_forecast,
                        lower_bound, upper_bound, confidence_level
                    FROM {self._RELATIONAL_POINT_TABLE}
                    WHERE scenario_id = ? AND version = ? AND indicator_code = ?
                    ORDER BY horizon
                    """,
                    [scenario_id, version, source_indicator_code],
                ).fetchall()
                if len(point_rows) != horizon_months:
                    raise RuntimeError(
                        "Normalized institutional macro scenario migration found "
                        f"{len(point_rows)} point(s) for {scenario_id} "
                        f"v{version} {indicator_code}; expected {horizon_months}"
                    )
                horizons = tuple(int(point[0]) for point in point_rows)
                expected_horizons = tuple(range(1, horizon_months + 1))
                if horizons != expected_horizons:
                    raise RuntimeError(
                        "Normalized institutional macro scenario migration found "
                        f"non-contiguous horizons for {scenario_id} v{version} "
                        f"{indicator_code}: {horizons}"
                    )

                points = tuple(
                    InstitutionalMacroScenarioPoint(
                        indicator_code=indicator_code,
                        horizon=int(point[0]),
                        target_period=self._required_date(
                            point[1],
                            context=(
                                f"{scenario_id} v{version} {indicator_code} " f"horizon {point[0]}"
                            ),
                        ),
                        point_forecast=float(point[2]),
                        lower_bound=(None if point[3] is None else float(point[3])),
                        upper_bound=(None if point[4] is None else float(point[4])),
                        confidence_level=float(point[5]),
                    )
                    for point in point_rows
                )

                indicators.append(
                    InstitutionalMacroScenarioIndicator(
                        indicator_code=indicator_code,
                        statistical_model_name=item[1],
                        statistical_model_family=item[2],
                        governance_model_name=item[3],
                        governance_model_family=item[4],
                        institutional_status=str(item[5]),
                        data_as_of_date=self._date_or_none(item[6]),
                        forecast_origin_period=self._date_or_none(item[7]),
                        last_observed_value=(None if item[8] is None else float(item[8])),
                        historical_observations=int(item[9]),
                        weighted_relative_score=(None if item[10] is None else float(item[10])),
                        improvement_vs_naive=(None if item[11] is None else float(item[11])),
                        dynamic_stability_status=item[12],
                        dynamic_stability_ratio=(None if item[13] is None else float(item[13])),
                        data_lag_days=(None if item[14] is None else int(item[14])),
                        data_lag_months=(None if item[15] is None else int(item[15])),
                        is_current_period=(None if item[16] is None else bool(item[16])),
                        approved_for_base_scenario=bool(item[17]),
                        reason_codes=self._decode_sequence_text(item[18]),
                        warnings=self._decode_sequence_text(item[19]),
                        points=points,
                        diagnostic=item[20],
                    )
                )

            scenario = InstitutionalMacroScenario(
                scenario_id=scenario_id,
                version=version,
                scenario_type=str(parent[2]),
                status=str(parent[3]),
                dataset_as_of_date=self._required_date(
                    parent[4],
                    context=f"{scenario_id} v{version} dataset",
                ),
                horizon_months=horizon_months,
                created_at=self._datetime(parent[6]),
                indicators=tuple(indicators),
                created_by=str(parent[7]),
                description=parent[8],
            )
            payloads.append((scenario_id, version, self._scenario_payload(scenario)))

        return tuple(payloads)

    def _install_reconstructed_payloads(
        self,
        *,
        payloads: tuple[tuple[str, int, str], ...],
        columns: Iterable[str],
    ) -> None:
        connection = self._database.connection
        column_lookup = {column.lower() for column in columns}
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute(
                "ALTER TABLE institutional_macro_scenarios "
                f"ADD COLUMN {self._PAYLOAD_COLUMN} VARCHAR"
            )
            if self._UPDATED_AT_COLUMN not in column_lookup:
                connection.execute(
                    "ALTER TABLE institutional_macro_scenarios "
                    f"ADD COLUMN {self._UPDATED_AT_COLUMN} TIMESTAMP"
                )
            for scenario_id, version, payload in payloads:
                connection.execute(
                    """
                    UPDATE institutional_macro_scenarios
                    SET scenario_payload_json = ?,
                        updated_at = COALESCE(updated_at, now())
                    WHERE scenario_id = ? AND version = ?
                    """,
                    [payload, scenario_id, version],
                )
            self._assert_no_missing_payloads()
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def _ensure_updated_at_column_if_required(
        self,
        columns: Iterable[str],
    ) -> None:
        if self._UPDATED_AT_COLUMN in {column.lower() for column in columns}:
            return
        connection = self._database.connection
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute(
                "ALTER TABLE institutional_macro_scenarios "
                f"ADD COLUMN {self._UPDATED_AT_COLUMN} TIMESTAMP"
            )
            connection.execute(
                "UPDATE institutional_macro_scenarios "
                f"SET {self._UPDATED_AT_COLUMN} = now() "
                f"WHERE {self._UPDATED_AT_COLUMN} IS NULL"
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def _assert_no_missing_payloads(self) -> None:
        missing = int(
            self._database.connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenarios "
                f"WHERE {self._PAYLOAD_COLUMN} IS NULL"
            ).fetchone()[0]
        )
        if missing:
            raise RuntimeError(
                "Legacy institutional macro scenario migration left "
                f"{missing} row(s) without a payload"
            )

    def _sync_legacy_workflow_tables_if_present(self) -> None:
        connection = self._database.connection
        has_audit = bool(self._table_columns(self._LEGACY_AUDIT_TABLE))
        has_reviews = bool(self._table_columns(self._LEGACY_REVIEW_TABLE))
        if not has_audit and not has_reviews:
            return

        connection.execute("BEGIN TRANSACTION")
        try:
            if has_audit:
                connection.execute(f"""
                    INSERT INTO institutional_macro_scenario_events (
                        event_id, scenario_id, version, event_type,
                        from_status, to_status, actor, event_at,
                        comment, reason
                    )
                    SELECT
                        legacy.event_id, legacy.scenario_id, legacy.version,
                        legacy.event_type, legacy.from_status, legacy.to_status,
                        legacy.actor, legacy.event_at, legacy.comment, legacy.reason
                    FROM {self._LEGACY_AUDIT_TABLE} legacy
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM institutional_macro_scenario_events current
                        WHERE current.event_id = legacy.event_id
                    )
                    """)
                missing_events = int(connection.execute(f"""
                        SELECT COUNT(*)
                        FROM {self._LEGACY_AUDIT_TABLE} legacy
                        LEFT JOIN institutional_macro_scenario_events current
                          ON current.event_id = legacy.event_id
                        WHERE current.event_id IS NULL
                        """).fetchone()[0])
                if missing_events:
                    raise RuntimeError(
                        "Institutional macro scenario audit migration left "
                        f"{missing_events} event(s) behind"
                    )

            if has_reviews:
                connection.execute(f"""
                    INSERT INTO institutional_macro_scenario_reviews (
                        scenario_id, version, indicator_code, resolution,
                        actor, resolved_at, comment, reason
                    )
                    SELECT
                        legacy.scenario_id, legacy.version,
                        legacy.indicator_code, legacy.resolution,
                        legacy.actor, legacy.resolved_at,
                        legacy.comment, legacy.reason
                    FROM {self._LEGACY_REVIEW_TABLE} legacy
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM institutional_macro_scenario_reviews current
                        WHERE current.scenario_id = legacy.scenario_id
                          AND current.version = legacy.version
                          AND current.indicator_code = legacy.indicator_code
                    )
                    """)
                missing_reviews = int(connection.execute(f"""
                        SELECT COUNT(*)
                        FROM {self._LEGACY_REVIEW_TABLE} legacy
                        LEFT JOIN institutional_macro_scenario_reviews current
                          ON current.scenario_id = legacy.scenario_id
                         AND current.version = legacy.version
                         AND current.indicator_code = legacy.indicator_code
                        WHERE current.scenario_id IS NULL
                        """).fetchone()[0])
                if missing_reviews:
                    raise RuntimeError(
                        "Institutional macro scenario review migration left "
                        f"{missing_reviews} resolution(s) behind"
                    )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def _table_column_names(self, table_name: str) -> tuple[str, ...]:
        rows = self._database.connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = ?
            ORDER BY ordinal_position
            """,
            [table_name],
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def _table_columns(self, table_name: str) -> frozenset[str]:
        return frozenset(column.lower() for column in self._table_column_names(table_name))

    @staticmethod
    def _required_date(value: Any, *, context: str) -> date:
        if value is None:
            raise RuntimeError(
                "Normalized institutional macro scenario migration found "
                f"a null required date for {context}"
            )
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _decode_sequence_text(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, (list, tuple)):
            return tuple(str(item) for item in value if str(item).strip())

        text = str(value).strip()
        if not text:
            return ()
        try:
            decoded = json.loads(text)
        except (TypeError, ValueError):
            decoded = None

        if isinstance(decoded, list):
            return tuple(str(item) for item in decoded if str(item).strip())
        if isinstance(decoded, str):
            normalized = decoded.strip()
            return (normalized,) if normalized else ()

        for separator in ("|", ";"):
            if separator in text:
                return tuple(item.strip() for item in text.split(separator) if item.strip())
        return (text,)

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
            if "json" in normalized and ("scenario" in normalized or "payload" in normalized):
                return column
        return None
