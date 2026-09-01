from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor


class HQLAExplanation:
    """Build readable explanations for HQLA outcomes."""

    def __init__(self) -> None:
        self._builder = ExplanationBuilder()

    def build(
        self,
        classification: str,
        score: Decimal,
        reason: str,
        assumptions: tuple[str, ...],
        warnings: tuple[str, ...],
        references: tuple[str, ...],
    ) -> Explanation:
        factors = [
            ExplanationFactor(
                name="hqla_score",
                value=score,
                direction="higher_is_better",
                contribution=score,
                source_reference="hqla",
            ),
        ]
        return self._builder.build(
            f"HQLA classification determined as {classification}",
            factors,
            assumptions=list(assumptions),
            warnings=list(warnings),
            source_references=list(references),
        )
