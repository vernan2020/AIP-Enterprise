from __future__ import annotations

from aip.domain.irrbb.models import BankingBookPosition
from aip.domain.irrbb.nii_run_specification import (
    NIIMethodologyRunResult,
    NIIMethodologyRunSpecification,
)
from aip.domain.irrbb.ports import (
    NIIExchangeRateProvider,
    NIIProjectionCapabilityEvidenceProvider,
    NIIProjectionRequirementProfileProvider,
    NIIProjectionStrategyResolver,
)
from aip.domain.irrbb.services.nii_scenario_set_evaluation_service import (
    NIIScenarioSetEvaluationService,
)


class NIIMethodologyRunService:
    """Execute an exact, pre-declared NII methodology run without choosing assumptions."""

    @classmethod
    def execute(
        cls,
        *,
        positions: tuple[BankingBookPosition, ...],
        specification: NIIMethodologyRunSpecification,
        profile_provider: NIIProjectionRequirementProfileProvider,
        capability_provider: NIIProjectionCapabilityEvidenceProvider,
        strategy_resolver: NIIProjectionStrategyResolver,
        exchange_rates: NIIExchangeRateProvider | None = None,
    ) -> NIIMethodologyRunResult:
        evaluation = NIIScenarioSetEvaluationService.evaluate(
            positions=positions,
            basis=specification.basis,
            stressed_scenarios=specification.stressed_scenarios,
            reporting_currency=specification.reporting_currency,
            profile_provider=profile_provider,
            capability_provider=capability_provider,
            strategy_resolver=strategy_resolver,
            exchange_rates=exchange_rates,
        )
        return NIIMethodologyRunResult(
            specification=specification,
            evaluation=evaluation,
        )
