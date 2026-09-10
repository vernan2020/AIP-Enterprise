from __future__ import annotations

from decimal import Decimal

from aip.domain.irrbb.models import IRRBBScenario
from aip.domain.irrbb.nii import (
    DeltaNIIResult,
    NIIScenarioAssessment,
    NetInterestIncomeResult,
)
from aip.shared.money import Money


class DeltaNIIService:
    """Compare BASE NII with an explicitly required set of stressed scenarios."""

    @classmethod
    def calculate(
        cls,
        *,
        base: NetInterestIncomeResult,
        stressed: tuple[NetInterestIncomeResult, ...],
        required_scenarios: tuple[IRRBBScenario, ...],
    ) -> DeltaNIIResult:
        if base.scenario is not IRRBBScenario.BASE:
            raise ValueError("base NII result must use the BASE scenario")
        if not required_scenarios:
            raise ValueError("required NII stress scenarios cannot be empty")
        if IRRBBScenario.BASE in required_scenarios:
            raise ValueError("required NII stress scenarios cannot include BASE")
        if len(set(required_scenarios)) != len(required_scenarios):
            raise ValueError("required NII stress scenarios cannot contain duplicates")

        by_scenario: dict[IRRBBScenario, NetInterestIncomeResult] = {}
        for result in stressed:
            if result.scenario is IRRBBScenario.BASE:
                raise ValueError("stressed NII results cannot include BASE")
            if result.reporting_currency is not base.reporting_currency:
                raise ValueError("all NII results must use the same reporting currency")
            if result.basis != base.basis:
                raise ValueError("all NII results must use the same projection basis")
            if result.scenario in by_scenario:
                raise ValueError(f"duplicate stressed NII scenario: {result.scenario.value}")
            by_scenario[result.scenario] = result

        required = set(required_scenarios)
        observed = set(by_scenario)
        missing = tuple(scenario for scenario in required_scenarios if scenario not in observed)
        if missing:
            names = ", ".join(scenario.value for scenario in missing)
            raise ValueError(f"missing required NII stress scenarios: {names}")

        unexpected = tuple(scenario for scenario in observed if scenario not in required)
        if unexpected:
            names = ", ".join(sorted(scenario.value for scenario in unexpected))
            raise ValueError(f"unexpected NII stress scenarios: {names}")

        assessments: list[NIIScenarioAssessment] = []
        for scenario in required_scenarios:
            result = by_scenario[scenario]
            delta = result.net_interest_income.amount - base.net_interest_income.amount
            fall = max(-delta, Decimal("0"))
            assessments.append(
                NIIScenarioAssessment(
                    scenario=scenario,
                    nii=result.net_interest_income,
                    delta_nii=Money(delta, base.reporting_currency),
                    fall_from_base=Money(fall, base.reporting_currency),
                )
            )

        worst = max(assessments, key=lambda item: item.fall_from_base.amount)
        return DeltaNIIResult(
            basis=base.basis,
            reporting_currency=base.reporting_currency,
            base_nii=base.net_interest_income,
            worst_scenario=worst.scenario,
            worst_loss=worst.fall_from_base,
            assessments=tuple(assessments),
        )
