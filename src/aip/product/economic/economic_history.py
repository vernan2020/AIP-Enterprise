from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(
    frozen=True,
    slots=True,
)
class EconomicHistoricalObservation:
    """
    Observación histórica económica normalizada.

    Representa una observación oficial ya transformada
    al código lógico utilizado por AIP Enterprise.
    """

    indicator_code: str
    observation_date: date
    value: Decimal
    source: str
    source_series_code: str | None
    unit: str
    frequency: str


@dataclass(
    frozen=True,
    slots=True,
)
class EconomicHistoricalSeries:
    """
    Serie histórica económica preparada para consumo analítico.

    No contiene forecasting ni transformaciones econométricas.
    """

    indicator_code: str

    observations: tuple[
        EconomicHistoricalObservation,
        ...,
    ]

    source: str

    @property
    def observation_count(
        self,
    ) -> int:
        return len(
            self.observations
        )

    @property
    def first_date(
        self,
    ) -> date | None:
        if not self.observations:
            return None

        return (
            self.observations[
                0
            ].observation_date
        )

    @property
    def last_date(
        self,
    ) -> date | None:
        if not self.observations:
            return None

        return (
            self.observations[
                -1
            ].observation_date
        )


@dataclass(
    frozen=True,
    slots=True,
)
class EconomicHistoricalSyncResult:
    """
    Resultado auditable de una sincronización histórica.
    """

    indicator_code: str
    observations_received: int
    observations_written: int
    first_date: date | None
    last_date: date | None
    status: str
    diagnostic: str | None = None
