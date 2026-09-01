from __future__ import annotations

from aip.product.configured.repositories.institutional_macro_scenario_compatibility_store import (
    InstitutionalMacroScenarioStore,
)
from aip.product.economic.institutional_macro_scenario import (
    InstitutionalMacroScenario,
)


class InstitutionalMacroScenarioRepository:
    """
    Repositorio de escenarios macroeconómicos institucionales.

    La política de construcción/aprobación pertenece a servicios
    de aplicación; este repositorio solamente persiste y consulta.
    """

    def __init__(
        self,
        *,
        store: InstitutionalMacroScenarioStore | None = None,
    ) -> None:
        self._store = (
            store
            or InstitutionalMacroScenarioStore()
        )

    @property
    def store(
        self,
    ) -> InstitutionalMacroScenarioStore:
        return self._store

    def save(
        self,
        scenario: InstitutionalMacroScenario,
    ) -> None:
        self._store.insert(
            scenario
        )

    def next_version(
        self,
        scenario_id: str,
    ) -> int:
        return self._store.next_version(
            scenario_id
        )

    def get(
        self,
        scenario_id: str,
        version: int,
    ) -> InstitutionalMacroScenario | None:
        return self._store.get(
            scenario_id,
            version,
        )

    def list_versions(
        self,
        scenario_id: str,
    ) -> tuple[InstitutionalMacroScenario, ...]:
        return self._store.list_versions(
            scenario_id
        )

    def statistics(
        self,
    ) -> dict[str, int]:
        return self._store.statistics()

    def save_review_resolution(
        self,
        resolution,
        event,
    ) -> None:
        self._store.save_review_resolution(
            resolution,
            event,
        )

    def approve_version(
        self,
        **kwargs,
    ) -> None:
        self._store.approve_version(
            **kwargs
        )

    def review_resolutions(
        self,
        scenario_id: str,
        version: int,
    ):
        return self._store.review_resolutions(
            scenario_id,
            version,
        )

    def audit_events(
        self,
        scenario_id: str,
        version: int,
    ):
        return self._store.audit_events(
            scenario_id,
            version,
        )

    def approved_versions_for_scenario(
        self,
        *,
        scenario_id: str,
        scenario_type: str,
    ) -> tuple[
        tuple[str, int],
        ...,
    ]:
        return (
            self._store
            .approved_versions_for_scenario(
                scenario_id=scenario_id,
                scenario_type=scenario_type,
            )
        )
