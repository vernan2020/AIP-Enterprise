from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import QApplication

from aip.application.irrbb import IRRBBAnalysisRequest, IRRBBSourceSnapshot
from aip.domain.irrbb.models import (
    BankingBookPosition,
    IRRBBCashFlow,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
)
from aip.domain.irrbb.services.scenario_evaluation_service import (
    IRRBBScenarioEvaluationService,
)
from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig
from aip.product.configured.irrbb import ConfiguredIRRBBRuntimeDependencies
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.shared.money import Currency, Money
from aip.ui.modules.rate_risk.views import RateRiskWorkspace
from aip.ui.shell.intelligence_main_window import FinancialIntelligenceMainWindow


class _EmptyGateway:
    def load_snapshot(self, *, cutoff_date: date) -> IRRBBSourceSnapshot:
        return IRRBBSourceSnapshot(cutoff_date=cutoff_date, position_records=())


class _RequestProvider:
    def request_for(self, *, cutoff_date: date) -> IRRBBAnalysisRequest:
        return IRRBBAnalysisRequest(
            cutoff_date=cutoff_date,
            reporting_currency=Currency.CRC,
            methodology=IRRBBMethodologyProfile(
                code="SUGEF-RTILB",
                version="PROPOSAL-2024",
                status=IRRBBMethodologyStatus.PROPOSED,
                source_reference="SUGEF Riesgo de mercado - Enero 2024",
            ),
        )


class _CapitalProvider:
    def tier_one_capital(
        self,
        *,
        cutoff_date: date,
        reporting_currency: Currency,
    ) -> Money:
        raise AssertionError("capital must not be requested for an empty RTILB perimeter")


class _NoopScenarioCashflows:
    def cashflows_for(
        self,
        *,
        position: BankingBookPosition,
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        return ()


class _UnitDiscountFactors:
    def discount_factor(
        self,
        *,
        currency: Currency,
        scenario: IRRBBScenario,
        valuation_date: date,
        payment_date: date,
    ) -> Decimal:
        return Decimal("1")


def _runtime_dependencies() -> ConfiguredIRRBBRuntimeDependencies:
    return ConfiguredIRRBBRuntimeDependencies(
        data_gateway=_EmptyGateway(),
        scenario_evaluation=IRRBBScenarioEvaluationService(
            scenario_cashflows=_NoopScenarioCashflows(),
            discount_factors=_UnitDiscountFactors(),
        ),
        tier_one_capital=_CapitalProvider(),
        request_provider=_RequestProvider(),
    )


def test_configured_shell_without_irrbb_runtime_remains_explicitly_unconfigured() -> None:
    app = QApplication.instance() or QApplication([])
    factory = DemoApplicationFactory(
        DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False),
        source_config=ConfiguredSourceConfig(),
    )
    window = FinancialIntelligenceMainWindow(demo_factory=factory)

    window.open_workspace("rate_risk")
    workspace = window.workspace.currentWidget()

    assert isinstance(workspace, RateRiskWorkspace)
    assert workspace.is_configured is False
    assert workspace.view._analysis_status_label.text() == "Estado: Sin cálculo"
    assert all(label.text() == "N/D" for label in workspace.view._kpi_values.values())

    window.close()
    app.processEvents()


def test_configured_shell_connects_irrbb_runtime_and_refreshes_active_cutoff() -> None:
    app = QApplication.instance() or QApplication([])
    factory = DemoApplicationFactory(
        DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False),
        source_config=ConfiguredSourceConfig(),
        irrbb_runtime_dependencies=_runtime_dependencies(),
    )
    window = FinancialIntelligenceMainWindow(demo_factory=factory)

    window.open_workspace("rate_risk")
    workspace = window.workspace.currentWidget()

    assert isinstance(workspace, RateRiskWorkspace)
    assert workspace.is_configured is True
    assert workspace.view._analysis_status_label.text() == "Estado: Sin datos"
    assert all(label.text() == "N/D" for label in workspace.view._kpi_values.values())

    new_cutoff = date(2026, 9, 30)
    factory.set_data_cutoff_date(new_cutoff)
    window._valuation_context.set_valuation_date(new_cutoff)
    workspace.refresh()

    assert workspace.view._cutoff_label.text() == "Corte: 30/09/2026"
    assert workspace.view._analysis_status_label.text() == "Estado: Sin datos"

    window.close()
    app.processEvents()
