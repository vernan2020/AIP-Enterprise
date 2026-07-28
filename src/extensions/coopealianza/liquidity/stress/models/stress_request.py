from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.domain.liquidity.cashflow.models.projection_result import ProjectionResult
from aip.domain.liquidity.gap.models.gap_result import GapResult
from src.extensions.coopealianza.liquidity.stress.configuration.stress_policy_config import StressPolicyConfig
from src.extensions.coopealianza.liquidity.stress.providers.scenario_provider import ScenarioProvider


@dataclass(frozen=True, slots=True)
class StressRequest:
    """Request payload for liquidity stress evaluation."""

    portfolio_reference: str
    configuration: StressPolicyConfig | None = None
    gap_result: GapResult | None = None
    projection_result: ProjectionResult | None = None
    scenario_provider: ScenarioProvider | None = None
    policy_context: dict[str, Any] = field(default_factory=dict)
