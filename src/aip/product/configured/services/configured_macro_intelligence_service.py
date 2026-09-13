from __future__ import annotations

from dataclasses import asdict
from typing import Any

from aip.product.configured.repositories.institutional_macro_scenario_repository import (
    InstitutionalMacroScenarioRepository,
)
from aip.product.economic.institutional_macro_driver_service import (
    InstitutionalMacroDriverService,
)


class ConfiguredMacroIntelligenceService:
    """Read-only application service for the governed macro scenario shown in UI."""

    DEFAULT_SCENARIO_ID = "BASE-MACRO-INSTITUTIONAL"

    def __init__(
        self,
        *,
        repository: InstitutionalMacroScenarioRepository | None = None,
    ) -> None:
        self._repository = repository or InstitutionalMacroScenarioRepository()
        self._driver_service = InstitutionalMacroDriverService(repository=self._repository)

    def get_projection(
        self,
        *,
        scenario_id: str = DEFAULT_SCENARIO_ID,
    ) -> dict[str, Any]:
        versions = self._repository.list_versions(scenario_id)
        approved = tuple(item for item in versions if str(item.status).upper() == "APPROVED")
        if not approved:
            return {
                "status": "UNAVAILABLE",
                "scenario_id": scenario_id,
                "diagnostic": "No approved institutional macro scenario is available",
                "rows": [],
            }

        scenario = max(approved, key=lambda item: int(item.version))
        drivers = self._driver_service.build_from_scenario(scenario)
        return {
            "status": "AVAILABLE",
            "scenario_id": drivers.scenario_id,
            "version": drivers.scenario_version,
            "scenario_type": drivers.scenario_type,
            "scenario_status": drivers.scenario_status,
            "dataset_as_of_date": drivers.dataset_as_of_date,
            "horizon": drivers.horizon,
            "rows": [asdict(row) for row in drivers.rows],
        }
