from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from aip.infrastructure.configuration.models import DatabaseSettings
from aip.infrastructure.database.manager import DatabaseManager
from aip.product.economic.institutional_macro_scenario import (
    InstitutionalMacroScenario,
    InstitutionalMacroScenarioIndicator,
    InstitutionalMacroScenarioPoint,
)
from aip.product.economic.institutional_macro_scenario_workflow import (
    ScenarioReviewResolution,
    ScenarioWorkflowEvent,
)


class InstitutionalMacroScenarioStore:
    """Persistent, auditable store for institutional macro scenarios.

    Forecast trajectories are stored as immutable JSON payloads while lifecycle
    status, human review resolutions and workflow events are persisted in
    dedicated relational tables.  Lifecycle changes are transactional and never
    rewrite the original forecast payload.
    """

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        database_settings: DatabaseSettings | None = None,
    ) -> None:
        if project_root is None:
            project_root = Path(__file__).resolve().parents[5]
        self._project_root = project_root
        self._database = DatabaseManager(
            database_settings or DatabaseSettings(),
            project_root,
        )
        self._initialized = False

    @property
    def database_path(self) -> Path:
        return self._database.path

    def initialize(self) -> None:
        if self._initialized:
            return
        self._database.initialize()
        self._create_schema()
        self._initialized = True

    def close(self) -> None:
        if not self._initialized:
            return
        self._database.close()
        self._initialized = False

    def __enter__(self) -> "InstitutionalMacroScenarioStore":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _create_schema(self) -> None:
        connection = self._database.connection
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS institutional_macro_scenarios (
                scenario_id VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                scenario_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                dataset_as_of_date DATE NOT NULL,
                horizon_months INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL,
                created_by VARCHAR NOT NULL,
                description VARCHAR,
                scenario_payload_json VARCHAR NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (scenario_id, version)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_macro_scenario_status
            ON institutional_macro_scenarios (
                scenario_id, scenario_type, status, version
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS institutional_macro_scenario_reviews (
                scenario_id VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                indicator_code VARCHAR NOT NULL,
                resolution VARCHAR NOT NULL,
                actor VARCHAR NOT NULL,
                resolved_at TIMESTAMP NOT NULL,
                comment VARCHAR NOT NULL,
                reason VARCHAR NOT NULL,
                PRIMARY KEY (scenario_id, version, indicator_code)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS institutional_macro_scenario_events (
                event_id VARCHAR PRIMARY KEY,
                scenario_id VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                event_type VARCHAR NOT NULL,
                from_status VARCHAR,
                to_status VARCHAR,
                actor VARCHAR NOT NULL,
                event_at TIMESTAMP NOT NULL,
                comment VARCHAR,
                reason VARCHAR
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_macro_scenario_events_version
            ON institutional_macro_scenario_events (
                scenario_id, version, event_at
            )
            """
        )

    @staticmethod
    def _normalize_scenario_id(value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("scenario_id cannot be empty")
        return normalized

    @staticmethod
    def _point_payload(point: InstitutionalMacroScenarioPoint) -> dict[str, Any]:
        return {
            "indicator_code": point.indicator_code,
            "horizon": point.horizon,
            "target_period": point.target_period.isoformat(),
            "point_forecast": point.point_forecast,
            "lower_bound": point.lower_bound,
            "upper_bound": point.upper_bound,
            "confidence_level": point.confidence_level,
        }

    @classmethod
    def _indicator_payload(
        cls,
        item: InstitutionalMacroScenarioIndicator,
    ) -> dict[str, Any]:
        return {
            "indicator_code": item.indicator_code,
            "statistical_model_name": item.statistical_model_name,
            "statistical_model_family": item.statistical_model_family,
            "governance_model_name": item.governance_model_name,
            "governance_model_family": item.governance_model_family,
            "institutional_status": item.institutional_status,
            "data_as_of_date": (
                item.data_as_of_date.isoformat()
                if item.data_as_of_date is not None
                else None
            ),
            "forecast_origin_period": (
                item.forecast_origin_period.isoformat()
                if item.forecast_origin_period is not None
                else None
            ),
            "last_observed_value": item.last_observed_value,
            "historical_observations": item.historical_observations,
            "weighted_relative_score": item.weighted_relative_score,
            "improvement_vs_naive": item.improvement_vs_naive,
            "dynamic_stability_status": item.dynamic_stability_status,
            "dynamic_stability_ratio": item.dynamic_stability_ratio,
            "data_lag_days": item.data_lag_days,
            "data_lag_months": item.data_lag_months,
            "is_current_period": item.is_current_period,
            "approved_for_base_scenario": item.approved_for_base_scenario,
            "reason_codes": list(item.reason_codes),
            "warnings": list(item.warnings),
            "points": [cls._point_payload(point) for point in item.points],
            "diagnostic": item.diagnostic,
        }

    @classmethod
    def _scenario_payload(cls, scenario: InstitutionalMacroScenario) -> str:
        payload = {
            "scenario_id": scenario.scenario_id,
            "version": scenario.version,
            "scenario_type": scenario.scenario_type,
            "dataset_as_of_date": scenario.dataset_as_of_date.isoformat(),
            "horizon_months": scenario.horizon_months,
            "created_at": scenario.created_at.isoformat(),
            "created_by": scenario.created_by,
            "description": scenario.description,
            "indicators": [cls._indicator_payload(item) for item in scenario.indicators],
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _date_or_none(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))

    @classmethod
    def _scenario_from_payload(
        cls,
        payload_json: str,
        *,
        status: str,
    ) -> InstitutionalMacroScenario:
        payload = json.loads(payload_json)
        indicators = []
        for item in payload.get("indicators", []):
            points = tuple(
                InstitutionalMacroScenarioPoint(
                    indicator_code=str(point["indicator_code"]),
                    horizon=int(point["horizon"]),
                    target_period=date.fromisoformat(str(point["target_period"])),
                    point_forecast=float(point["point_forecast"]),
                    lower_bound=(
                        None if point.get("lower_bound") is None
                        else float(point["lower_bound"])
                    ),
                    upper_bound=(
                        None if point.get("upper_bound") is None
                        else float(point["upper_bound"])
                    ),
                    confidence_level=float(point["confidence_level"]),
                )
                for point in item.get("points", [])
            )
            indicators.append(
                InstitutionalMacroScenarioIndicator(
                    indicator_code=str(item["indicator_code"]),
                    statistical_model_name=item.get("statistical_model_name"),
                    statistical_model_family=item.get("statistical_model_family"),
                    governance_model_name=item.get("governance_model_name"),
                    governance_model_family=item.get("governance_model_family"),
                    institutional_status=str(item["institutional_status"]),
                    data_as_of_date=cls._date_or_none(item.get("data_as_of_date")),
                    forecast_origin_period=cls._date_or_none(
                        item.get("forecast_origin_period")
                    ),
                    last_observed_value=(
                        None if item.get("last_observed_value") is None
                        else float(item["last_observed_value"])
                    ),
                    historical_observations=int(item["historical_observations"]),
                    weighted_relative_score=(
                        None if item.get("weighted_relative_score") is None
                        else float(item["weighted_relative_score"])
                    ),
                    improvement_vs_naive=(
                        None if item.get("improvement_vs_naive") is None
                        else float(item["improvement_vs_naive"])
                    ),
                    dynamic_stability_status=item.get("dynamic_stability_status"),
                    dynamic_stability_ratio=(
                        None if item.get("dynamic_stability_ratio") is None
                        else float(item["dynamic_stability_ratio"])
                    ),
                    data_lag_days=(
                        None if item.get("data_lag_days") is None
                        else int(item["data_lag_days"])
                    ),
                    data_lag_months=(
                        None if item.get("data_lag_months") is None
                        else int(item["data_lag_months"])
                    ),
                    is_current_period=item.get("is_current_period"),
                    approved_for_base_scenario=bool(
                        item["approved_for_base_scenario"]
                    ),
                    reason_codes=tuple(str(x) for x in item.get("reason_codes", [])),
                    warnings=tuple(str(x) for x in item.get("warnings", [])),
                    points=points,
                    diagnostic=item.get("diagnostic"),
                )
            )
        return InstitutionalMacroScenario(
            scenario_id=str(payload["scenario_id"]),
            version=int(payload["version"]),
            scenario_type=str(payload["scenario_type"]),
            status=status,
            dataset_as_of_date=date.fromisoformat(str(payload["dataset_as_of_date"])),
            horizon_months=int(payload["horizon_months"]),
            created_at=cls._datetime(payload["created_at"]),
            indicators=tuple(indicators),
            created_by=str(payload["created_by"]),
            description=payload.get("description"),
        )

    def insert(self, scenario: InstitutionalMacroScenario) -> None:
        self.initialize()
        scenario_id = self._normalize_scenario_id(scenario.scenario_id)
        if scenario.version < 1:
            raise ValueError("scenario version must be >= 1")
        if scenario.status != "DRAFT":
            raise ValueError("new institutional scenarios must be persisted as DRAFT")
        connection = self._database.connection
        try:
            connection.execute("BEGIN TRANSACTION")
            exists = connection.execute(
                """
                SELECT 1 FROM institutional_macro_scenarios
                WHERE scenario_id = ? AND version = ?
                """,
                [scenario_id, scenario.version],
            ).fetchone()
            if exists is not None:
                raise ValueError(
                    f"Scenario version already exists: {scenario_id} v{scenario.version}"
                )
            connection.execute(
                """
                INSERT INTO institutional_macro_scenarios (
                    scenario_id, version, scenario_type, status,
                    dataset_as_of_date, horizon_months, created_at, created_by,
                    description, scenario_payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                """,
                [
                    scenario_id,
                    scenario.version,
                    scenario.scenario_type,
                    scenario.status,
                    scenario.dataset_as_of_date,
                    scenario.horizon_months,
                    scenario.created_at,
                    scenario.created_by,
                    scenario.description,
                    self._scenario_payload(scenario),
                ],
            )
            self._insert_event(
                ScenarioWorkflowEvent(
                    event_id=uuid4().hex,
                    scenario_id=scenario_id,
                    version=scenario.version,
                    event_type="CREATED",
                    from_status=None,
                    to_status="DRAFT",
                    actor=scenario.created_by,
                    event_at=scenario.created_at,
                    comment=scenario.description,
                    reason="Institutional macro scenario created",
                )
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def next_version(self, scenario_id: str) -> int:
        self.initialize()
        normalized = self._normalize_scenario_id(scenario_id)
        row = self._database.connection.execute(
            """
            SELECT COALESCE(MAX(version), 0) + 1
            FROM institutional_macro_scenarios WHERE scenario_id = ?
            """,
            [normalized],
        ).fetchone()
        return int(row[0])

    def get(self, scenario_id: str, version: int) -> InstitutionalMacroScenario | None:
        self.initialize()
        normalized = self._normalize_scenario_id(scenario_id)
        row = self._database.connection.execute(
            """
            SELECT scenario_payload_json, status
            FROM institutional_macro_scenarios
            WHERE scenario_id = ? AND version = ?
            """,
            [normalized, version],
        ).fetchone()
        if row is None:
            return None
        return self._scenario_from_payload(str(row[0]), status=str(row[1]))

    def list_versions(self, scenario_id: str) -> tuple[InstitutionalMacroScenario, ...]:
        self.initialize()
        normalized = self._normalize_scenario_id(scenario_id)
        rows = self._database.connection.execute(
            """
            SELECT scenario_payload_json, status
            FROM institutional_macro_scenarios
            WHERE scenario_id = ? ORDER BY version
            """,
            [normalized],
        ).fetchall()
        return tuple(
            self._scenario_from_payload(str(row[0]), status=str(row[1])) for row in rows
        )

    def statistics(self) -> dict[str, int]:
        self.initialize()
        connection = self._database.connection
        total = int(connection.execute(
            "SELECT COUNT(*) FROM institutional_macro_scenarios"
        ).fetchone()[0])
        approved = int(connection.execute(
            "SELECT COUNT(*) FROM institutional_macro_scenarios WHERE status = 'APPROVED'"
        ).fetchone()[0])
        drafts = int(connection.execute(
            "SELECT COUNT(*) FROM institutional_macro_scenarios WHERE status = 'DRAFT'"
        ).fetchone()[0])
        superseded = int(connection.execute(
            "SELECT COUNT(*) FROM institutional_macro_scenarios WHERE status = 'SUPERSEDED'"
        ).fetchone()[0])
        return {
            "scenarios": total,
            "drafts": drafts,
            "approved": approved,
            "superseded": superseded,
        }

    def save_review_resolution(
        self,
        resolution: ScenarioReviewResolution,
        event: ScenarioWorkflowEvent,
    ) -> None:
        self.initialize()
        scenario = self.get(resolution.scenario_id, resolution.version)
        if scenario is None:
            raise ValueError("Scenario version does not exist")
        if scenario.status != "DRAFT":
            raise ValueError("Review resolution requires DRAFT status")
        connection = self._database.connection
        try:
            connection.execute("BEGIN TRANSACTION")
            connection.execute(
                """
                INSERT INTO institutional_macro_scenario_reviews (
                    scenario_id, version, indicator_code, resolution,
                    actor, resolved_at, comment, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (scenario_id, version, indicator_code)
                DO UPDATE SET
                    resolution = excluded.resolution,
                    actor = excluded.actor,
                    resolved_at = excluded.resolved_at,
                    comment = excluded.comment,
                    reason = excluded.reason
                """,
                [
                    self._normalize_scenario_id(resolution.scenario_id),
                    resolution.version,
                    resolution.indicator_code.strip().upper(),
                    resolution.resolution,
                    resolution.actor,
                    resolution.resolved_at,
                    resolution.comment,
                    resolution.reason,
                ],
            )
            self._insert_event(event)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def review_resolutions(
        self,
        scenario_id: str,
        version: int,
    ) -> tuple[ScenarioReviewResolution, ...]:
        self.initialize()
        normalized = self._normalize_scenario_id(scenario_id)
        rows = self._database.connection.execute(
            """
            SELECT scenario_id, version, indicator_code, resolution,
                   actor, resolved_at, comment, reason
            FROM institutional_macro_scenario_reviews
            WHERE scenario_id = ? AND version = ?
            ORDER BY indicator_code
            """,
            [normalized, version],
        ).fetchall()
        return tuple(
            ScenarioReviewResolution(
                scenario_id=str(row[0]),
                version=int(row[1]),
                indicator_code=str(row[2]),
                resolution=str(row[3]),
                actor=str(row[4]),
                resolved_at=self._datetime(row[5]),
                comment=str(row[6]),
                reason=str(row[7]),
            )
            for row in rows
        )

    def _insert_event(self, event: ScenarioWorkflowEvent) -> None:
        self._database.connection.execute(
            """
            INSERT INTO institutional_macro_scenario_events (
                event_id, scenario_id, version, event_type,
                from_status, to_status, actor, event_at, comment, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event.event_id,
                self._normalize_scenario_id(event.scenario_id),
                event.version,
                event.event_type,
                event.from_status,
                event.to_status,
                event.actor,
                event.event_at,
                event.comment,
                event.reason,
            ],
        )

    def audit_events(
        self,
        scenario_id: str,
        version: int,
    ) -> tuple[ScenarioWorkflowEvent, ...]:
        self.initialize()
        normalized = self._normalize_scenario_id(scenario_id)
        rows = self._database.connection.execute(
            """
            SELECT event_id, scenario_id, version, event_type,
                   from_status, to_status, actor, event_at, comment, reason
            FROM institutional_macro_scenario_events
            WHERE scenario_id = ? AND version = ?
            ORDER BY event_at, event_id
            """,
            [normalized, version],
        ).fetchall()
        return tuple(
            ScenarioWorkflowEvent(
                event_id=str(row[0]),
                scenario_id=str(row[1]),
                version=int(row[2]),
                event_type=str(row[3]),
                from_status=None if row[4] is None else str(row[4]),
                to_status=None if row[5] is None else str(row[5]),
                actor=str(row[6]),
                event_at=self._datetime(row[7]),
                comment=None if row[8] is None else str(row[8]),
                reason=None if row[9] is None else str(row[9]),
            )
            for row in rows
        )

    def approved_versions_for_scenario(
        self,
        *,
        scenario_id: str,
        scenario_type: str,
    ) -> tuple[tuple[str, int], ...]:
        self.initialize()
        normalized_id = self._normalize_scenario_id(scenario_id)
        normalized_type = scenario_type.strip().upper()
        rows = self._database.connection.execute(
            """
            SELECT scenario_id, version
            FROM institutional_macro_scenarios
            WHERE scenario_id = ? AND scenario_type = ? AND status = 'APPROVED'
            ORDER BY version
            """,
            [normalized_id, normalized_type],
        ).fetchall()
        return tuple((str(row[0]), int(row[1])) for row in rows)

    def approve_version(
        self,
        *,
        scenario_id: str,
        version: int,
        actor: str,
        approved_at: datetime,
        comment: str,
        reason: str,
        approved_event: ScenarioWorkflowEvent,
        superseded_events: Iterable[ScenarioWorkflowEvent],
    ) -> None:
        del actor, approved_at, comment, reason  # represented by immutable audit events
        self.initialize()
        normalized = self._normalize_scenario_id(scenario_id)
        connection = self._database.connection
        try:
            connection.execute("BEGIN TRANSACTION")
            row = connection.execute(
                """
                SELECT status FROM institutional_macro_scenarios
                WHERE scenario_id = ? AND version = ?
                """,
                [normalized, version],
            ).fetchone()
            if row is None:
                raise ValueError("Scenario version does not exist")
            if str(row[0]) != "DRAFT":
                raise ValueError("Only DRAFT scenarios can be approved")

            for event in tuple(superseded_events):
                result = connection.execute(
                    """
                    UPDATE institutional_macro_scenarios
                    SET status = 'SUPERSEDED', updated_at = now()
                    WHERE scenario_id = ? AND version = ? AND status = 'APPROVED'
                    """,
                    [
                        self._normalize_scenario_id(event.scenario_id),
                        event.version,
                    ],
                )
                del result
                self._insert_event(event)

            connection.execute(
                """
                UPDATE institutional_macro_scenarios
                SET status = 'APPROVED', updated_at = now()
                WHERE scenario_id = ? AND version = ?
                """,
                [normalized, version],
            )
            self._insert_event(approved_event)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
