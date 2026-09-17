from __future__ import annotations

from dataclasses import dataclass

from ..base.policy_result import PolicyResult


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Aggregated evaluation report for a set of policies."""

    results: tuple[PolicyResult, ...]
    overall_status: str
    message: str
