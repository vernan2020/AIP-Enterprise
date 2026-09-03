from __future__ import annotations

from aip.core.container import Container
from aip.product.configured.bootstrap.configured_dependency_composition import (
    ConfiguredDependencyComposition,
)
from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
)
from aip.product.configured.services.configured_financial_analysis_service import (
    ConfiguredFinancialAnalysisService,
)
from aip.product.configured.services.configured_macro_intelligence_service import (
    ConfiguredMacroIntelligenceService,
)
from aip.product.demo.configuration.demo_config import DemoConfig


def test_configured_composition_registers_financial_and_macro_services() -> None:
    container = ConfiguredDependencyComposition(
        DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False),
        ConfiguredSourceConfig(),
    ).compose(Container())

    assert isinstance(
        container.resolve(ConfiguredFinancialAnalysisService),
        ConfiguredFinancialAnalysisService,
    )
    assert isinstance(
        container.resolve(ConfiguredMacroIntelligenceService),
        ConfiguredMacroIntelligenceService,
    )
