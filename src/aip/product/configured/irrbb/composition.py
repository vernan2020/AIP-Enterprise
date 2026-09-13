from __future__ import annotations

from aip.application.irrbb import (
    IRRBBAnalysisRequestProvider,
    IRRBBDataGateway,
    LoadIRRBBSourceSnapshot,
    RunIRRBBAnalysis,
)
from aip.core.container import Container
from aip.domain.irrbb.ports import TierOneCapitalProvider
from aip.domain.irrbb.services.scenario_evaluation_service import (
    IRRBBScenarioEvaluationService,
)
from aip.product.configured.irrbb.runtime_dependencies import (
    ConfiguredIRRBBRuntimeDependencies,
)


class ConfiguredIRRBBComposition:
    """Compose the optional configured RTILB runtime into the application container.

    No physical source is selected here. The supplied runtime dependencies must
    already satisfy the source-agnostic application/domain ports, allowing XML,
    SQL Server, PostgreSQL, OneDrive/Excel or another approved adapter later.
    """

    def __init__(
        self,
        runtime_dependencies: ConfiguredIRRBBRuntimeDependencies | None = None,
    ) -> None:
        self._runtime_dependencies = runtime_dependencies

    def compose(self, container: Container) -> bool:
        dependencies = self._runtime_dependencies
        if dependencies is None:
            return False

        source_loader = LoadIRRBBSourceSnapshot(dependencies.data_gateway)
        analysis = RunIRRBBAnalysis(
            source_loader=source_loader,
            scenario_evaluation=dependencies.scenario_evaluation,
            tier_one_capital=dependencies.tier_one_capital,
        )

        container.register_instance(ConfiguredIRRBBRuntimeDependencies, dependencies)
        container.register_instance(IRRBBDataGateway, dependencies.data_gateway)
        container.register_instance(
            IRRBBAnalysisRequestProvider,
            dependencies.request_provider,
        )
        container.register_instance(
            IRRBBScenarioEvaluationService,
            dependencies.scenario_evaluation,
        )
        container.register_instance(TierOneCapitalProvider, dependencies.tier_one_capital)
        container.register_instance(LoadIRRBBSourceSnapshot, source_loader)
        container.register_instance(RunIRRBBAnalysis, analysis)
        return True
