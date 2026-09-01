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
        connection.execute(
            """
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
            """
        )
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
        row = connection.execute(
            """
            SELECT scenario_json, scenario_payload_json, status
            FROM institutional_macro_scenarios
            WHERE scenario_id = 'BASE-MACRO-INSTITUTIONAL' AND version = 4
            """
        ).fetchone()
    finally:
        connection.close()

    assert "scenario_json" in columns
    assert "scenario_payload_json" in columns
    assert row is not None
    assert row[0] == row[1]
    assert row[2] == "APPROVED"


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
