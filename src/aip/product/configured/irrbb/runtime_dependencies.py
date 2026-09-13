from __future__ import annotations

from dataclasses import dataclass

from aip.application.irrbb import IRRBBAnalysisRequestProvider, IRRBBDataGateway
from aip.domain.irrbb.ports import TierOneCapitalProvider
from aip.domain.irrbb.services.scenario_evaluation_service import (
    IRRBBScenarioEvaluationService,
)


@dataclass(frozen=True, slots=True)
class ConfiguredIRRBBRuntimeDependencies:
    """Source-agnostic outer-layer dependencies required to activate RTILB.

    Physical technologies are deliberately absent from this contract. A future
    XML, SQL Server, PostgreSQL or OneDrive/Excel implementation must satisfy the
    declared ports before the configured application composition consumes it.
    """

    data_gateway: IRRBBDataGateway
    scenario_evaluation: IRRBBScenarioEvaluationService
    tier_one_capital: TierOneCapitalProvider
    request_provider: IRRBBAnalysisRequestProvider
