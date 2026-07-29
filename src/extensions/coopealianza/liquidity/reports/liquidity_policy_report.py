from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.policies.base.policy_result import PolicyResult


@dataclass(frozen=True, slots=True)
class LiquidityPolicyReport:
    """Immutable institutional liquidity policy report."""

    evaluation_date: datetime
    portfolio_reference: str
    policy_configuration_version: str
    total_policies_evaluated: int
    passed_count: int
    failed_count: int
    warning_count: int
    not_applicable_count: int
    blocking_failures: tuple[str, ...] = ()
    affected_assets: tuple[str, ...] = ()
    affected_issuers: tuple[str, ...] = ()
    policy_references: tuple[tuple[str, str], ...] = ()
    evidence: tuple[dict[str, Any], ...] = ()
    recommended_actions: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    calculation_identifier: str = ""
    evaluations: tuple[PolicyResult, ...] = ()
    explanation: Explanation | None = None
