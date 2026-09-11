from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import duckdb

from aip.infrastructure.configuration.models import DatabaseSettings
from aip.product.configured.repositories.institutional_macro_scenario_compatibility_store import (
    InstitutionalMacroScenarioStore,
)
from aip.product.configured.services.configured_macro_intelligence_service import (
    ConfiguredMacroIntelligenceService,
)
from aip.product.economic.institutional_macro_scenario import InstitutionalMacroScenario


def _payload(*, version: int = 4) -> str:
    return json.dumps(
        {
            "scenario_id": "BASE-MACRO-INSTITUTIONAL",
            "version": version,
            "scenario_type": "BASE",
            "dataset_as_of_date": "2026-08-27",
            "horizon_months": 12,
            "created_at": "2026-08-27T12:00:00",
            "created_by": "TEST",
            "description": "legacy persisted scenario",
            "indicators": [
                {
                    "indicator_code": "TPM",
                    "statistical_model_name": "ARIMA",
                    "statistical_model_family": "ARIMA",
                    "governance_model_name": "ARIMA",
                    "governance_model_family": "ARIMA",
                    "institutional_status": "APPROVED",
                    "data_as_of_date": "2026-08-27",
                    "forecast_origin_period": "2026-08-01",
                    "last_observed_value": 3.25,
                    "historical_observations": 36,
                    "weighted_relative_score": 0.10,
                    "improvement_vs_naive": 0.20,
                    "dynamic_stability_status": "STABLE",
                    "dynamic_stability_ratio": 1.0,
                    "data_lag_days": 0,
                    "data_lag_months": 0,
                    "is_current_period": True,
                    "approved_for_base_scenario": True,
                    "reason_codes": [],
                    "warnings": [],
                    "points": [
                        {
                            "indicator_code": "TPM",
                            "horizon": 1,
                            "target_period": "2026-09-01",
                            "point_forecast": 3.25,
                            "lower_bound": 3.00,
                            "upper_bound": 3.50,
                            "confidence_level": 0.95,
                        }
                    ],
                    "diagnostic": None,
                }
            ],
        },
        separators=(",", ":"),
    )


def _scenario(*, version: int, status: str) -> InstitutionalMacroScenario:
    return InstitutionalMacroScenario(
        scenario_id="BASE-MACRO-INSTITUTIONAL",
        version=version,
        scenario_type="BASE",
        status=status,
        dataset_as_of_date=date(2026, 8, 27),
        horizon_months=12,
        created_at=datetime(2026, 8, 27, 12, 0, 0),
        indicators=(),
        created_by="TEST",
        description=None,
    )


def test_store_migrates_legacy_scenario_json_column_without_losing_row(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "legacy_macro.duckdb"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute("""
            CREATE TABLE institutional_macro_scenarios (
                scenario_id VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                scenario_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                dataset_as_of_date DATE NOT NULL,
                horizon_months INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL,
                created_by VARCHAR NOT NULL,
                description VARCHAR,
                scenario_json VARCHAR NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (scenario_id, version)
            )
            """)
        connection.execute(
            """
            INSERT INTO institutional_macro_scenarios (
                scenario_id, version, scenario_type, status,
                dataset_as_of_date, horizon_months, created_at, created_by,
                description, scenario_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "BASE-MACRO-INSTITUTIONAL",
                4,
                "BASE",
                "APPROVED",
                date(2026, 8, 27),
                12,
                datetime(2026, 8, 27, 12, 0, 0),
                "TEST",
                "legacy persisted scenario",
                _payload(version=4),
            ],
        )
    finally:
        connection.close()

    store = InstitutionalMacroScenarioStore(
        project_root=tmp_path,
        database_settings=DatabaseSettings(path=Path("database/legacy_macro.duckdb")),
    )
    scenario = store.get("BASE-MACRO-INSTITUTIONAL", 4)
    store.close()

    assert scenario is not None
    assert scenario.version == 4
    assert scenario.status == "APPROVED"
    assert scenario.indicator_count == 1

    connection = duckdb.connect(str(database_path))
    try:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info('institutional_macro_scenarios')"
            ).fetchall()
        }
        row = connection.execute("""
            SELECT scenario_json, scenario_payload_json, status
            FROM institutional_macro_scenarios
            WHERE scenario_id = 'BASE-MACRO-INSTITUTIONAL' AND version = 4
            """).fetchone()
    finally:
        connection.close()

    assert "scenario_json" in columns
    assert "scenario_payload_json" in columns
    assert row is not None
    assert row[0] == row[1]
    assert row[2] == "APPROVED"


def _create_normalized_legacy_schema(database_path: Path) -> None:
    indicator_codes = (
        "FX_SELL",
        "TPM",
        "TBP",
        "TRI_CRC_12M",
        "TRI_USD_12M",
        "INFLATION",
        "IMAE",
    )
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute("""
            CREATE TABLE institutional_macro_scenarios (
                scenario_id VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                scenario_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                dataset_as_of_date DATE NOT NULL,
                horizon_months INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL,
                created_by VARCHAR NOT NULL,
                description VARCHAR,
                PRIMARY KEY (scenario_id, version)
            )
            """)
        connection.execute("""
            CREATE TABLE institutional_macro_scenario_indicators (
                scenario_id VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                indicator_code VARCHAR NOT NULL,
                statistical_model_name VARCHAR,
                statistical_model_family VARCHAR,
                governance_model_name VARCHAR,
                governance_model_family VARCHAR,
                institutional_status VARCHAR NOT NULL,
                data_as_of_date DATE,
                forecast_origin_period DATE,
                last_observed_value DOUBLE,
                historical_observations INTEGER NOT NULL,
                weighted_relative_score DOUBLE,
                improvement_vs_naive DOUBLE,
                dynamic_stability_status VARCHAR,
                dynamic_stability_ratio DOUBLE,
                data_lag_days INTEGER,
                data_lag_months INTEGER,
                is_current_period BOOLEAN,
                approved_for_base_scenario BOOLEAN NOT NULL,
                reason_codes VARCHAR NOT NULL,
                warnings VARCHAR NOT NULL,
                diagnostic VARCHAR,
                PRIMARY KEY (scenario_id, version, indicator_code)
            )
            """)
        connection.execute("""
            CREATE TABLE institutional_macro_scenario_points (
                scenario_id VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                indicator_code VARCHAR NOT NULL,
                horizon INTEGER NOT NULL,
                target_period DATE NOT NULL,
                point_forecast DOUBLE NOT NULL,
                lower_bound DOUBLE,
                upper_bound DOUBLE,
                confidence_level DOUBLE NOT NULL,
                PRIMARY KEY (scenario_id, version, indicator_code, horizon)
            )
            """)
        connection.execute("""
            CREATE TABLE institutional_macro_scenario_audit (
                event_id VARCHAR NOT NULL,
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
            """)
        connection.execute("""
            CREATE TABLE institutional_macro_scenario_review_resolutions (
                scenario_id VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                indicator_code VARCHAR NOT NULL,
                resolution VARCHAR NOT NULL,
                actor VARCHAR NOT NULL,
                resolved_at TIMESTAMP NOT NULL,
                comment VARCHAR NOT NULL,
                reason VARCHAR NOT NULL
            )
            """)

        for version, status in ((3, "SUPERSEDED"), (4, "APPROVED")):
            connection.execute(
                """
                INSERT INTO institutional_macro_scenarios
                VALUES (?, ?, 'BASE', ?, ?, 12, ?, 'AIP_SYSTEM', ?)
                """,
                [
                    "BASE-MACRO-INSTITUTIONAL",
                    version,
                    status,
                    date(2026, 8, 27),
                    datetime(2026, 8, 28, 12, version, 0),
                    "Institutional macroeconomic base scenario",
                ],
            )
            for offset, indicator_code in enumerate(indicator_codes):
                reason_codes = '["MULTI_HORIZON_APPROVED"]' if offset % 2 else "MODEL_EQUIVALENCE"
                connection.execute(
                    """
                    INSERT INTO institutional_macro_scenario_indicators
                    VALUES (
                        ?, ?, ?, 'NAIVE', 'NAIVE', 'NAIVE', 'NAIVE',
                        'APPROVED', ?, ?, ?, 61, 1.0, 0.0,
                        'STABLE', 0.0, 0, 0, true, true, ?, '', ?
                    )
                    """,
                    [
                        "BASE-MACRO-INSTITUTIONAL",
                        version,
                        indicator_code,
                        date(2026, 8, 27),
                        date(2026, 8, 31),
                        float(offset + version),
                        reason_codes,
                        f"diagnostic-{indicator_code}",
                    ],
                )
                for horizon in range(1, 13):
                    month_index = 7 + horizon
                    target_period = date(
                        2026 + (month_index // 12),
                        (month_index % 12) + 1,
                        28,
                    )
                    point_forecast = float(offset + version) + horizon / 100.0
                    connection.execute(
                        """
                        INSERT INTO institutional_macro_scenario_points
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.95)
                        """,
                        [
                            "BASE-MACRO-INSTITUTIONAL",
                            version,
                            indicator_code,
                            horizon,
                            target_period,
                            point_forecast,
                            point_forecast - 0.25,
                            point_forecast + 0.25,
                        ],
                    )

        for version, event_type, from_status, to_status in (
            (3, "APPROVED", "DRAFT", "APPROVED"),
            (4, "APPROVED", "DRAFT", "APPROVED"),
        ):
            connection.execute(
                """
                INSERT INTO institutional_macro_scenario_audit
                VALUES (?, 'BASE-MACRO-INSTITUTIONAL', ?, ?, ?, ?,
                        'AIP_VALIDATION', ?, 'technical validation', 'test')
                """,
                [
                    f"event-{version}",
                    version,
                    event_type,
                    from_status,
                    to_status,
                    datetime(2026, 8, 28, 13, version, 0),
                ],
            )
        connection.execute(
            """
            INSERT INTO institutional_macro_scenario_review_resolutions
            VALUES (
                'BASE-MACRO-INSTITUTIONAL', 4, 'IMAE',
                'ACCEPTED_FOR_SCENARIO', 'AIP_VALIDATION', ?,
                'Technical workflow validation', 'test'
            )
            """,
            [datetime(2026, 8, 28, 13, 4, 0)],
        )
    finally:
        connection.close()


def test_store_migrates_normalized_relational_scenarios_and_workflow_history(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "normalized_macro.duckdb"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    _create_normalized_legacy_schema(database_path)
    settings = DatabaseSettings(path=Path("database/normalized_macro.duckdb"))

    store = InstitutionalMacroScenarioStore(
        project_root=tmp_path,
        database_settings=settings,
    )
    versions = store.list_versions("BASE-MACRO-INSTITUTIONAL")
    store.close()

    assert tuple(item.version for item in versions) == (3, 4)
    assert tuple(item.status for item in versions) == ("SUPERSEDED", "APPROVED")
    approved = versions[-1]
    assert approved.indicator_count == 7
    assert all(len(item.points) == 12 for item in approved.indicators)
    assert approved.indicator("FX_SELL") is not None
    assert approved.indicator("FX_SELL").reason_codes == ("MODEL_EQUIVALENCE",)
    assert approved.indicator("TPM") is not None
    assert approved.indicator("TPM").reason_codes == ("MULTI_HORIZON_APPROVED",)

    connection = duckdb.connect(str(database_path))
    try:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info('institutional_macro_scenarios')"
            ).fetchall()
        }
        counts = {
            "parents": connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenarios"
            ).fetchone()[0],
            "indicators": connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenario_indicators"
            ).fetchone()[0],
            "points": connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenario_points"
            ).fetchone()[0],
            "legacy_audit": connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenario_audit"
            ).fetchone()[0],
            "events": connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenario_events"
            ).fetchone()[0],
            "legacy_reviews": connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenario_review_resolutions"
            ).fetchone()[0],
            "reviews": connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenario_reviews"
            ).fetchone()[0],
        }
    finally:
        connection.close()

    assert {"scenario_payload_json", "updated_at"}.issubset(columns)
    assert counts == {
        "parents": 2,
        "indicators": 14,
        "points": 168,
        "legacy_audit": 2,
        "events": 2,
        "legacy_reviews": 1,
        "reviews": 1,
    }

    reopened = InstitutionalMacroScenarioStore(
        project_root=tmp_path,
        database_settings=settings,
    )
    reopened_versions = reopened.list_versions("BASE-MACRO-INSTITUTIONAL")
    reopened.close()
    assert len(reopened_versions) == 2

    connection = duckdb.connect(str(database_path))
    try:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenario_events"
            ).fetchone()[0]
            == 2
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM institutional_macro_scenario_reviews"
            ).fetchone()[0]
            == 1
        )
    finally:
        connection.close()


class _FakeRepository:
    def list_versions(self, scenario_id: str) -> tuple[InstitutionalMacroScenario, ...]:
        assert scenario_id == "BASE-MACRO-INSTITUTIONAL"
        return (
            _scenario(version=2, status="APPROVED"),
            _scenario(version=3, status="SUPERSEDED"),
            _scenario(version=4, status="APPROVED"),
        )


class _CapturingDriverService:
    def __init__(self) -> None:
        self.version: int | None = None

    def build_from_scenario(self, scenario: InstitutionalMacroScenario):
        self.version = scenario.version
        return SimpleNamespace(
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            scenario_type=scenario.scenario_type,
            scenario_status=scenario.status,
            dataset_as_of_date=scenario.dataset_as_of_date,
            horizon=scenario.horizon_months,
            rows=(),
        )


def test_macro_service_uses_scenario_object_contract_and_latest_approved() -> None:
    service = ConfiguredMacroIntelligenceService(repository=_FakeRepository())
    driver_service = _CapturingDriverService()
    service._driver_service = driver_service

    result = service.get_projection()

    assert result["status"] == "AVAILABLE"
    assert result["version"] == 4
    assert result["scenario_status"] == "APPROVED"
    assert driver_service.version == 4
