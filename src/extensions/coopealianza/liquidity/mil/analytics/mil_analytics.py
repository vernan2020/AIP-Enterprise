from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor


class MilAnalytics:
    """Build deterministic explainability for MIL eligibility decisions."""

    def __init__(self) -> None:
        self._builder = ExplanationBuilder()

    def build_explanation(
        self,
        *,
        conclusion: str,
        factors: list[tuple[str, Decimal]],
        source_references: list[str] | None = None,
    ) -> Explanation:
        explanation_factors = [
            ExplanationFactor(
                name=name,
                value=value,
                direction="increase",
                contribution=value,
                source_reference=source_reference,
            )
            for name, value, source_reference in [
                (name, value, source_reference)
                for name, value in factors
                for source_reference in [None]
            ]
        ]
        return self._builder.build(
            conclusion,
            explanation_factors,
            assumptions=["No FX conversion applied"],
            warnings=[],
            source_references=source_references or [],
        )
