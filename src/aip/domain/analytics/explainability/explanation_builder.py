from __future__ import annotations

from datetime import datetime

from aip.domain.analytics.exceptions import ExplainabilityError
from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor


class ExplanationBuilder:
    """Build deterministic, context-aware explanations."""

    def build(
        self,
        concise_conclusion: str,
        factors: list[ExplanationFactor],
        assumptions: list[str] | None = None,
        warnings: list[str] | None = None,
        source_references: list[str] | None = None,
    ) -> Explanation:
        if not concise_conclusion.strip():
            raise ExplainabilityError("Conclusion cannot be empty")
        if not factors:
            raise ExplainabilityError("At least one explanation factor is required")
        return Explanation(
            concise_conclusion=concise_conclusion,
            supporting_factors=tuple(factors),
            assumptions=tuple(assumptions or ()),
            warnings=tuple(warnings or ()),
            source_references=tuple(source_references or ()),
            calculation_timestamp=datetime.now(),
        )
