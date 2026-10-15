from __future__ import annotations

from datetime import date

from aip.product.configured.repositories.economic_historical_store import (
    EconomicHistoricalStore,
)
from aip.product.economic.economic_history import (
    EconomicHistoricalObservation,
    EconomicHistoricalSeries,
)


class EconomicHistoricalRepository:
    """
    Repositorio de acceso al histórico macroeconómico.

    Consume únicamente el store persistente.

    La sincronización BCCR se implementa en un componente separado
    para mantener separadas las responsabilidades de:
    - adquisición remota;
    - persistencia;
    - consulta analítica.
    """

    def __init__(
        self,
        *,
        store: EconomicHistoricalStore | None = None,
    ) -> None:
        self._store = store or EconomicHistoricalStore()

    @property
    def store(
        self,
    ) -> EconomicHistoricalStore:
        return self._store

    def get_series(
        self,
        indicator_code: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> EconomicHistoricalSeries:
        normalized_code = indicator_code.strip().upper()

        observations = self._store.observations_for_series(
            indicator_code=normalized_code,
            from_date=from_date,
            to_date=to_date,
        )

        source = observations[-1].source if observations else "UNKNOWN"

        return EconomicHistoricalSeries(
            indicator_code=normalized_code,
            observations=observations,
            source=source,
        )

    def get_recent_series(self, indicator_code: str, *, limit: int = 2) -> EconomicHistoricalSeries:
        """Load only the newest historical points for low-latency fallback."""
        normalized_code = indicator_code.strip().upper()
        observations = self._store.recent_observations_for_series(
            indicator_code=normalized_code, limit=limit
        )
        return EconomicHistoricalSeries(
            indicator_code=normalized_code,
            observations=observations,
            source=observations[-1].source if observations else "UNKNOWN",
        )

    def latest_available_date(
        self,
        indicator_code: str,
    ) -> date | None:
        observation = self._store.latest_observation(indicator_code=indicator_code)

        if observation is None:
            return None

        return observation.observation_date

    def latest_available_dates(
        self,
        indicator_codes: tuple[str, ...],
    ) -> dict[str, date | None]:
        """Resolve all latest observation dates with one read-only aggregate."""
        normalized_codes = tuple(code.strip().upper() for code in indicator_codes)
        found = self._store.latest_observation_dates(normalized_codes)
        return {code: found.get(code) for code in normalized_codes}

    def available_series(
        self,
    ) -> tuple[str, ...]:
        return self._store.series_codes()

    def statistics(
        self,
    ) -> dict[str, int]:
        return self._store.statistics()

    def append(
        self,
        observations: tuple[
            EconomicHistoricalObservation,
            ...,
        ],
    ) -> int:
        """
        Punto explícito de escritura utilizado por los servicios
        de sincronización.

        Este repositorio no realiza llamadas remotas.
        """
        return self._store.upsert_observations(observations)
