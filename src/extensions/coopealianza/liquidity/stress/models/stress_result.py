from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from src.extensions.coopealianza.liquidity.stress.models.stress_scenario_result import (
    StressScenarioResult,
)


@dataclass(frozen=True, slots=True)
class StressResult:
    """Aggregated liquidity stress evaluation result."""

    portfolio_reference: str
    configuration_version: str
    total_scenarios: int
    scenario_results: tuple[StressScenarioResult, ...] = field(default_factory=tuple)
    summary: dict[str, Decimal] = field(default_factory=dict)
    explanation: Any | None = None
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    stressed_parameters: dict[str, Decimal] = field(default_factory=dict)
    policy_references: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    affected_assets: tuple[str, ...] = field(default_factory=tuple)
    affected_buckets: tuple[str, ...] = field(default_factory=tuple)
    calculation_identifier: str = ""
