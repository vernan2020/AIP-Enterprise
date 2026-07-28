from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor


@dataclass(frozen=True, slots=True)
class RecommendationExplanation:
    """Immutable explanation object tailored for recommendations."""

    concise_conclusion: str
    supporting_factors: tuple[object, ...]
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()

    def to_explanation(self) -> Explanation:
        factors = [factor for factor in (self._coerce_factor(item) for item in self.supporting_factors) if factor is not None]
        if not factors:
            factors.append(ExplanationFactor(name="default", value=Decimal("0"), direction="neutral", contribution=Decimal("0")))
        return ExplanationBuilder().build(
            self.concise_conclusion,
            factors,
            assumptions=list(self.assumptions),
            warnings=list(self.warnings),
            source_references=list(self.source_references),
        )

    @property
    def supporting_factor_objects(self) -> tuple[ExplanationFactor, ...]:
        return tuple(
            factor for factor in (self._coerce_factor(item) for item in self.supporting_factors) if factor is not None
        )

    def _coerce_factor(self, factor: object) -> ExplanationFactor | None:
        if isinstance(factor, ExplanationFactor):
            return factor
        if isinstance(factor, dict):
            return ExplanationFactor(
                name=str(factor.get("name", "factor")),
                value=Decimal(str(factor.get("value", Decimal("0")))),
                direction=str(factor.get("direction", "neutral")),
                contribution=Decimal(str(factor.get("contribution", Decimal("0")))),
                source_reference=factor.get("source_reference"),
            )
        return None
