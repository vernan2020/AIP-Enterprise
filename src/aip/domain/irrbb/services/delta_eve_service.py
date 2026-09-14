from __future__ import annotations

from decimal import Decimal

from aip.domain.irrbb.models import (
    STANDARD_STRESS_SCENARIOS,
    DeltaEVEResult,
    EconomicValueResult,
    IRRBBScenario,
    ScenarioAssessment,
)
from aip.shared.money import Money


class DeltaEVEExposureService:
    """Compare base EVE with six stresses and identify the maximum EVE fall."""

    @classmethod
    def calculate(
        cls,
        *,
        base: EconomicValueResult,
        stressed: tuple[EconomicValueResult, ...],
        tier_one_capital: Money,
        required_scenarios: tuple[IRRBBScenario, ...] = STANDARD_STRESS_SCENARIOS,
    ) -> DeltaEVEResult:
        if base.scenario is not IRRBBScenario.BASE:
            raise ValueError("base result must use the BASE scenario")
        if tier_one_capital.currency is not base.reporting_currency:
            raise ValueError("Tier 1 capital currency must match EVE reporting currency")
        if tier_one_capital.amount <= 0:
            raise ValueError("Tier 1 capital must be positive")

        by_scenario: dict[IRRBBScenario, EconomicValueResult] = {}
        for result in stressed:
            if result.reporting_currency is not base.reporting_currency:
                raise ValueError("all EVE results must use the same reporting currency")
            if result.scenario is IRRBBScenario.BASE:
                raise ValueError("stressed results cannot include BASE")
            if result.scenario in by_scenario:
                raise ValueError(f"duplicate stressed scenario: {result.scenario.value}")
            by_scenario[result.scenario] = result

        missing = tuple(scenario for scenario in required_scenarios if scenario not in by_scenario)
        if missing:
            names = ", ".join(value.value for value in missing)
            raise ValueError(f"missing required IRRBB stress scenarios: {names}")

        assessments: list[ScenarioAssessment] = []
        for scenario in required_scenarios:
            result = by_scenario[scenario]
            delta = result.eve.amount - base.eve.amount
            fall = max(base.eve.amount - result.eve.amount, Decimal("0"))
            assessments.append(
                ScenarioAssessment(
                    scenario=scenario,
                    eve=result.eve,
                    delta_eve=Money(delta, base.reporting_currency),
                    fall_from_base=Money(fall, base.reporting_currency),
                )
            )

        worst = max(assessments, key=lambda item: item.fall_from_base.amount)
        exposure_ratio = worst.fall_from_base.amount / tier_one_capital.amount
        return DeltaEVEResult(
            reporting_currency=base.reporting_currency,
            base_eve=base.eve,
            tier_one_capital=tier_one_capital,
            worst_scenario=worst.scenario,
            worst_loss=worst.fall_from_base,
            exposure_ratio_to_tier1=exposure_ratio,
            assessments=tuple(assessments),
        )
