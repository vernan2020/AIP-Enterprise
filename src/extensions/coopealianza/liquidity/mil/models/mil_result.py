from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.extensions.coopealianza.liquidity.mil.models.mil_capacity_result import MilCapacityResult
from src.extensions.coopealianza.liquidity.mil.models.mil_position_result import MilPositionResult


@dataclass(frozen=True, slots=True)
class MilResult:
    portfolio_reference: str
    configuration_version: str
    calculation_date: Any
    total_assets_evaluated: int
    positions: tuple[MilPositionResult, ...] = field(default_factory=tuple)
    capacity: MilCapacityResult = field(default_factory=MilCapacityResult)
    status_counts: dict[str, int] = field(default_factory=dict)
    policy_references: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    recommended_actions: tuple[str, ...] = field(default_factory=tuple)
    explanation: Any | None = None
    calculation_identifier: str = ""
