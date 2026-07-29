from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.domain.liquidity.cashflow.models.projection_result import ProjectionResult
from aip.domain.liquidity.gap.models.gap_result import GapResult
from aip.domain.liquidity.hqla.models.hqla_result import HQLAResult
from aip.domain.policies.base.policy_result import PolicyResult
from aip.domain.relative_value.models.relative_value_result import RelativeValueResult
from src.extensions.coopealianza.liquidity.mil.models.mil_result import MilResult
from src.extensions.coopealianza.liquidity.stress.models.stress_result import StressResult
from src.extensions.coopealianza.treasury.decision.configuration.decision_config import (
    DecisionConfig,
)


@dataclass(frozen=True, slots=True)
class TreasuryDecisionRequest:
    """Input bundle for treasury recommendation generation."""

    portfolio_reference: str
    correlation_id: str = ""
    calculation_id: str = ""
    decision_horizon: str = "T+1"
    policy_results: tuple[PolicyResult, ...] = field(default_factory=tuple)
    portfolio_result: Any | None = None
    pricing_result: Any | None = None
    relative_value_result: RelativeValueResult | None = None
    hqla_result: HQLAResult | None = None
    mil_result: MilResult | None = None
    cash_flow_result: ProjectionResult | None = None
    gap_result: GapResult | None = None
    stress_result: StressResult | None = None
    projection_result: ProjectionResult | None = None
    configuration: DecisionConfig | dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.projection_result is not None and self.cash_flow_result is None:
            object.__setattr__(self, "cash_flow_result", self.projection_result)
