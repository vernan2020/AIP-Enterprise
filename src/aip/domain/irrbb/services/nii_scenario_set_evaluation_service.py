from __future__ import annotations

from aip.domain.irrbb.models import BankingBookPosition, IRRBBScenario
from aip.domain.irrbb.nii import NetInterestIncomeResult, NIIProjectionBasis
from aip.domain.irrbb.nii_certification import NIIProjectionCertificationStatus
from aip.domain.irrbb.nii_scenario_set import (
    NIIScenarioSetEvaluationResult,
    NIIScenarioSetEvaluationStatus,
)
from aip.domain.irrbb.ports import (
    NIIExchangeRateProvider,
    NIIProjectionCapabilityEvidenceProvider,
    NIIProjectionRequirementProfileProvider,
    NIIProjectionStrategyResolver,
)
from aip.domain.irrbb.services.delta_nii_service import DeltaNIIService
from aip.domain.irrbb.services.net_interest_income_service import NetInterestIncomeService
from aip.domain.irrbb.services.nii_projection_certification_service import (
    NIIProjectionCertificationService,
)
from aip.shared.money import Currency


class NIIScenarioSetEvaluationService:
    """Evaluate BASE and explicit stressed NII scenarios without choosing assumptions."""

    @classmethod
    def evaluate(
        cls,
        *,
        positions: tuple[BankingBookPosition, ...],
        basis: NIIProjectionBasis,
        stressed_scenarios: tuple[IRRBBScenario, ...],
        reporting_currency: Currency,
        profile_provider: NIIProjectionRequirementProfileProvider,
        capability_provider: NIIProjectionCapabilityEvidenceProvider,
        strategy_resolver: NIIProjectionStrategyResolver,
        exchange_rates: NIIExchangeRateProvider | None = None,
    ) -> NIIScenarioSetEvaluationResult:
        if not stressed_scenarios:
            raise ValueError("NII scenario-set evaluation requires stressed scenarios")
        if IRRBBScenario.BASE in stressed_scenarios:
            raise ValueError("NII stressed scenarios cannot include BASE")
        if len(set(stressed_scenarios)) != len(stressed_scenarios):
            raise ValueError("NII stressed scenarios cannot contain duplicates")

        scenarios = (IRRBBScenario.BASE, *stressed_scenarios)
        certifications = tuple(
            NIIProjectionCertificationService.project_certified(
                positions=positions,
                basis=basis,
                scenario=scenario,
                profile_provider=profile_provider,
                capability_provider=capability_provider,
                strategy_resolver=strategy_resolver,
            )
            for scenario in scenarios
        )

        if any(item.status is NIIProjectionCertificationStatus.BLOCKED for item in certifications):
            return NIIScenarioSetEvaluationResult(
                basis=basis,
                reporting_currency=reporting_currency,
                required_stressed_scenarios=stressed_scenarios,
                status=NIIScenarioSetEvaluationStatus.BLOCKED,
                certifications=certifications,
            )

        if all(
            item.status is NIIProjectionCertificationStatus.NO_INCLUDED_POSITIONS
            for item in certifications
        ):
            return NIIScenarioSetEvaluationResult(
                basis=basis,
                reporting_currency=reporting_currency,
                required_stressed_scenarios=stressed_scenarios,
                status=NIIScenarioSetEvaluationStatus.NO_INCLUDED_POSITIONS,
                certifications=certifications,
            )

        if any(
            item.status is NIIProjectionCertificationStatus.NO_INCLUDED_POSITIONS
            for item in certifications
        ):
            raise ValueError("inconsistent NII scenario certification scope across scenarios")

        scenario_results: list[NetInterestIncomeResult] = []
        for certification in certifications:
            projection_batch = certification.projection_batch
            if projection_batch is None:
                raise ValueError("projected NII certification requires projection_batch")
            accruals = projection_batch.accruals
            if not accruals:
                raise ValueError(
                    "projected NII scenario contains no accruals; zero-NII policy is not defined"
                )
            scenario_results.append(
                NetInterestIncomeService.calculate(
                    accruals=accruals,
                    basis=basis,
                    scenario=certification.scenario,
                    reporting_currency=reporting_currency,
                    exchange_rates=exchange_rates,
                )
            )

        base_result = scenario_results[0]
        stressed_results = tuple(scenario_results[1:])
        delta_nii = DeltaNIIService.calculate(
            base=base_result,
            stressed=stressed_results,
            required_scenarios=stressed_scenarios,
        )
        return NIIScenarioSetEvaluationResult(
            basis=basis,
            reporting_currency=reporting_currency,
            required_stressed_scenarios=stressed_scenarios,
            status=NIIScenarioSetEvaluationStatus.EVALUATED,
            certifications=certifications,
            scenario_results=tuple(scenario_results),
            delta_nii=delta_nii,
        )
