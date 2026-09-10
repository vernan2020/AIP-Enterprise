from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.application.irrbb.analysis_contracts import (
    IRRBBAnalysisRequest,
    IRRBBAnalysisStatus,
)
from aip.application.irrbb.contracts import IRRBBSourceSnapshot
from aip.application.irrbb.ports import IRRBBAnalysisRequestProvider
from aip.application.irrbb.run_analysis import RunIRRBBAnalysis
from aip.core.container import Container, ServiceNotRegisteredError
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
from aip.product.configured.irrbb import (
    ConfiguredIRRBBComposition,
    ConfiguredIRRBBRuntimeDependencies,
)
from aip.shared.money import Currency, Money


_CUTOFF = date(2026, 8, 31)
_METHODOLOGY = IRRBBMethodologyProfile(
    code="SUGEF-RTILB",
    version="PROPOSAL-2024",
    status=IRRBBMethodologyStatus.PROPOSED,
    source_reference="SUGEF Riesgo de mercado - Enero 2024",
)


class _EmptyGateway:
    def load_snapshot(self, *, cutoff_date: date) -> IRRBBSourceSnapshot:
        return IRRBBSourceSnapshot(cutoff_date=cutoff_date, position_records=())


class _RequestProvider:
    def request_for(self, *, cutoff_date: date) -> IRRBBAnalysisRequest:
        return IRRBBAnalysisRequest(
            cutoff_date=cutoff_date,
            reporting_currency=Currency.CRC,
            methodology=_METHODOLOGY,
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


def test_configured_irrbb_composition_is_optional() -> None:
    container = Container()

    assert ConfiguredIRRBBComposition().compose(container) is False
    try:
        container.resolve(RunIRRBBAnalysis)
    except ServiceNotRegisteredError:
        pass
    else:
        raise AssertionError("RunIRRBBAnalysis must remain unregistered without RTILB runtime")


def test_configured_irrbb_composition_registers_source_agnostic_runtime() -> None:
    container = Container()

    assert ConfiguredIRRBBComposition(_runtime_dependencies()).compose(container) is True

    request_provider = container.resolve(IRRBBAnalysisRequestProvider)
    result = container.resolve(RunIRRBBAnalysis).execute(
        request_provider.request_for(cutoff_date=_CUTOFF)
    )

    assert result.status is IRRBBAnalysisStatus.NO_DATA
    assert result.evaluation is None
    assert result.source_load.snapshot.cutoff_date == _CUTOFF
    assert result.source_load.snapshot.position_records == ()
