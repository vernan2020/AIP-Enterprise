from __future__ import annotations

from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor


class ProjectionExplanation:
    """Build an explanation for a projected cash flow run."""

    def build(self, concise_conclusion: str, factors: list[ExplanationFactor], assumptions: tuple[str, ...] = (), warnings: tuple[str, ...] = (), references: tuple[str, ...] = ()) -> object:
        return ExplanationBuilder().build(
            concise_conclusion,
            factors,
            assumptions=list(assumptions),
            warnings=list(warnings),
            source_references=list(references),
        )
