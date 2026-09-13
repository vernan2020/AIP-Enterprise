from __future__ import annotations

from typing import Protocol

from aip.domain.intelligence.models import FinancialIntelligenceContext


class FinancialIntelligenceContextProvider(Protocol):
    """Read-only port that exposes certified AIP data to the intelligence use case."""

    def load(self) -> FinancialIntelligenceContext: ...
