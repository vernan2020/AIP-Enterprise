from __future__ import annotations

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.ui.services.diagnostic_service import ProductionReadinessService


def test_production_readiness_uses_injected_application_factory() -> None:
    factory = DemoApplicationFactory(DemoConfig())
    service = ProductionReadinessService(
        iterations=1,
        application_factory=factory,
    )

    assert service._factory is factory


def test_diagnostic_snapshot_uses_factory_runtime_metadata() -> None:
    factory = DemoApplicationFactory(DemoConfig())
    service = ProductionReadinessService(
        iterations=1,
        application_factory=factory,
    )

    snapshot = service.diagnostic_snapshot()

    assert snapshot["execution_mode"] == factory.config.execution_mode
    assert snapshot["environment"] == factory.config.environment_name
    assert snapshot["valuation_date"] == factory.config.data_cutoff_date.isoformat()
