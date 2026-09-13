from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from aip.domain.irrbb.models import (
    DeltaEVEResult,
    EconomicValueResult,
    IRRBBMethodologyProfile,
    IRRBBScenario,
)
from aip.shared.money import Currency


@dataclass(frozen=True, slots=True)
class IRRBBScenarioEvaluationResult:
    """Auditable BASE + stress EVE evaluation for one methodology and cutoff."""

    methodology: IRRBBMethodologyProfile
    valuation_date: date
    reporting_currency: Currency
    position_count: int
    base: EconomicValueResult
    stressed: tuple[EconomicValueResult, ...]
    exposure: DeltaEVEResult

    def __post_init__(self) -> None:
        if self.position_count <= 0:
            raise ValueError("scenario evaluation position_count must be positive")
        if self.base.scenario is not IRRBBScenario.BASE:
            raise ValueError("scenario evaluation base result must use BASE")
        if self.base.reporting_currency is not self.reporting_currency:
            raise ValueError("base EVE reporting currency does not match evaluation")
        if self.exposure.reporting_currency is not self.reporting_currency:
            raise ValueError("Delta EVE reporting currency does not match evaluation")
        for result in self.stressed:
            if result.scenario is IRRBBScenario.BASE:
                raise ValueError("stressed evaluation cannot contain BASE")
            if result.reporting_currency is not self.reporting_currency:
                raise ValueError("stressed EVE reporting currency does not match evaluation")
