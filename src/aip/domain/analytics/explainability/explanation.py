from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor


@dataclass(frozen=True, slots=True)
class Explanation:
    """Immutable explanation object for analytical results."""

    concise_conclusion: str
    supporting_factors: tuple[ExplanationFactor, ...]
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()
    calculation_timestamp: datetime | None = None
