from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.policies.base.policy_result import PolicyResult


@dataclass(frozen=True, slots=True)
class HQLAPolicyResult:
    """Container for policy evaluation outcomes used by HQLA classification."""

    policy_results: tuple[PolicyResult, ...]
    total_score: Decimal
