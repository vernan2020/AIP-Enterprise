from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.economic.economic_indicator_catalog import EconomicIndicatorDefinition
from aip.domain.economic.economic_indicator_observation import EconomicIndicatorObservation


@dataclass(frozen=True, slots=True)
class EconomicIndicatorSeries:
    """Normalized historical series for one economic indicator."""

    definition: EconomicIndicatorDefinition
    observations: tuple[EconomicIndicatorObservation, ...]

    @property
    def latest(self) -> EconomicIndicatorObservation | None:
        if not self.observations:
            return None
        return max(self.observations, key=lambda item: item.observation_date)

    @property
    def previous(self) -> EconomicIndicatorObservation | None:
        ordered = sorted(
            self.observations,
            key=lambda item: item.observation_date,
            reverse=True,
        )
        return ordered[1] if len(ordered) >= 2 else None

    @property
    def absolute_change(self) -> Decimal | None:
        latest = self.latest
        previous = self.previous
        if latest is None or previous is None:
            return None
        return latest.value - previous.value

    @property
    def relative_change_percent(self) -> Decimal | None:
        latest = self.latest
        previous = self.previous
        if latest is None or previous is None or previous.value == 0:
            return None
        return ((latest.value - previous.value) / abs(previous.value)) * Decimal("100")

    @property
    def trend(self) -> str:
        change = self.absolute_change
        if change is None:
            return "UNAVAILABLE"
        if change > 0:
            return "UP"
        if change < 0:
            return "DOWN"
        return "STABLE"
