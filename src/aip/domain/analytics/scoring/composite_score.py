from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.exceptions import InvalidScoreBandError, ScoringError
from aip.domain.analytics.scoring.score_band import ScoreBand
from aip.domain.analytics.scoring.weighted_score import WeightedScore


@dataclass(frozen=True, slots=True)
class CompositeScore:
    """Composite score aggregating multiple weighted-score groups."""

    final_score: Decimal
    score_scale: tuple[Decimal, Decimal]
    score_bands: tuple[ScoreBand, ...]
    weighted_scores: tuple[WeightedScore, ...]
    explanation: tuple[str, ...] = ()

    def determine_band(self, value: Decimal) -> ScoreBand | None:
        for band in self.score_bands:
            if band.contains(value):
                return band
        raise InvalidScoreBandError("No score band matches the provided value")
