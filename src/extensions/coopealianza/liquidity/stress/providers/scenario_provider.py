from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.extensions.coopealianza.liquidity.stress.configuration.stress_policy_config import StressScenarioConfig


class ScenarioProvider(ABC):
    """Provider for scenario definitions."""

    @abstractmethod
    def get_scenarios(self) -> tuple[StressScenarioConfig, ...]:
        """Return the configured scenarios."""


class StaticScenarioProvider(ScenarioProvider):
    """Provider that uses a fixed tuple of scenarios."""

    def __init__(self, scenarios: tuple[StressScenarioConfig, ...] | None = None) -> None:
        self._scenarios = scenarios or ()

    def get_scenarios(self) -> tuple[StressScenarioConfig, ...]:
        return self._scenarios
