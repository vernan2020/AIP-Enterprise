from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.relative_value.enums.confidence_level import ConfidenceLevel


@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    """Score confidence based on evidence completeness and quality."""

    evidence_quality: Decimal
    evidence_completeness: Decimal
    policy_alignment: Decimal

    def __post_init__(self) -> None:
        for value in (self.evidence_quality, self.evidence_completeness, self.policy_alignment):
            if not value.is_finite() or value < 0 or value > 1:
                raise ValueError("Confidence components must be finite values between 0 and 1")

    @property
    def level(self) -> ConfidenceLevel:
        average = (
            self.evidence_quality + self.evidence_completeness + self.policy_alignment
        ) / Decimal("3")
        if average >= Decimal("0.8"):
            return ConfidenceLevel.HIGH
        if average >= Decimal("0.5"):
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    @property
    def score(self) -> Decimal:
        return (
            self.evidence_quality + self.evidence_completeness + self.policy_alignment
        ) / Decimal("3")
