from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.application.contracts.analysis_result import AnalysisResult
from aip.application.exceptions import OrchestratorExecutionError
from aip.application.orchestrators.investment_decision_orchestrator import (
    InvestmentDecisionOrchestrator,
)
from aip.application.orchestrators.liquidity_analysis_orchestrator import (
    LiquidityAnalysisOrchestrator,
)
from aip.application.orchestrators.portfolio_analysis_orchestrator import (
    PortfolioAnalysisOrchestrator,
)
from aip.application.orchestrators.pricing_orchestrator import PricingOrchestrator
from aip.application.workflows.hqla_workflow import HQLAWorkflow
from aip.application.workflows.liquidity_workflow import LiquidityWorkflow
from aip.application.workflows.relative_value_workflow import RelativeValueWorkflow
from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.shared.conventions import DayCountConvention


class _Instrument(GovernmentBond):
    def __init__(self) -> None:
        issuer = Issuer(code="gov", name="Government", issuer_type=IssuerType.GOVERNMENT)
        super().__init__(
            isin="US123",
            name="Stub Bond",
            issuer=issuer,
            currency="USD",
            settlement_calendar="USD",
            business_day_convention="FOLLOWING",
            day_count_convention=DayCountConvention.ACTUAL_365,
            issue_date=date(2020, 1, 1),
            settlement_date=date(2020, 1, 3),
            maturity_date=date(2030, 1, 1),
            coupon_schedule=None,
            nominal_value=Decimal("1000000"),
            book_value=Decimal("1000000"),
            market_value=Decimal("1000000"),
            face_value=Decimal("1000000"),
            outstanding_amount=Decimal("1000000"),
            yield_rate=Decimal("0.03"),
            duration=Decimal("4"),
            modified_duration=Decimal("4"),
            convexity=Decimal("0.5"),
            dirty_price=Decimal("1000000"),
            clean_price=Decimal("1000000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.05"),
        )


def _make_request(**overrides: Any) -> AnalysisRequest:
    curve = YieldCurve(
        valuation_date=date(2026, 1, 1),
        currency="USD",
        points=(
            CurvePoint(tenor=Decimal("1"), zero_rate=Decimal("0.03")),
            CurvePoint(tenor=Decimal("10"), zero_rate=Decimal("0.04")),
        ),
    )
    request = AnalysisRequest(
        workflow_id="wf-1",
        correlation_id="corr-1",
        valuation_date=date(2026, 1, 1),
        instrument=_Instrument(),
        market_yield=Decimal("0.04"),
        curve=curve,
        market_price=Decimal("1000000"),
        benchmark_yield=Decimal("0.05"),
        calculation_id="calc-1",
        requested_at=datetime(2026, 1, 1, tzinfo=UTC),
        context={
            "contractual_cashflows": (
                CashFlow(
                    payment_date=date(2026, 6, 1),
                    amount=Decimal("100000"),
                    currency="USD",
                    cash_flow_type="coupon",
                ),
            )
        },
    )
    for key, value in overrides.items():
        setattr(request, key, value)
    return request


class _StubWorkflow:
    def __init__(self, result: AnalysisResult) -> None:
        self._result = result

    def execute(self, request: AnalysisRequest) -> AnalysisResult:
        return self._result


def test_all_orchestrators_coordinate_successfully() -> None:
    request = _make_request()
    pricing = PricingOrchestrator(
        workflow=_StubWorkflow(
            AnalysisResult(
                workflow_id="wf", correlation_id="corr", status="COMPLETED", result={"ok": True}
            )
        )
    )
    portfolio = PortfolioAnalysisOrchestrator(
        workflow=_StubWorkflow(
            AnalysisResult(
                workflow_id="wf", correlation_id="corr", status="COMPLETED", result={"ok": True}
            )
        )
    )
    liquidity = LiquidityAnalysisOrchestrator(
        workflow=_StubWorkflow(
            AnalysisResult(
                workflow_id="wf", correlation_id="corr", status="COMPLETED", result={"ok": True}
            )
        )
    )
    investment = InvestmentDecisionOrchestrator(
        workflow=_StubWorkflow(
            AnalysisResult(
                workflow_id="wf", correlation_id="corr", status="COMPLETED", result={"ok": True}
            )
        )
    )

    assert pricing.execute(request).status == "COMPLETED"
    assert portfolio.execute(request).status == "COMPLETED"
    assert liquidity.execute(request).status == "COMPLETED"
    assert investment.execute(request).status == "COMPLETED"


def test_orchestrators_translate_domain_failures() -> None:
    request = _make_request()

    class _FailingWorkflow:
        def execute(self, request: AnalysisRequest) -> AnalysisResult:
            raise ValueError("invalid")

    with pytest.raises(OrchestratorExecutionError):
        PricingOrchestrator(workflow=_FailingWorkflow()).execute(request)


def test_relative_value_liquidity_and_hqla_workflows_execute_through_domain_engines() -> None:
    request = _make_request()

    relative_result = RelativeValueWorkflow().execute(request)
    liquidity_result = LiquidityWorkflow().execute(request)
    hqla_result = HQLAWorkflow().execute(request)

    assert relative_result.status == "COMPLETED"
    assert liquidity_result.status == "COMPLETED"
    assert hqla_result.status == "COMPLETED"
    assert relative_result.correlation_id == request.correlation_id
    assert liquidity_result.correlation_id == request.correlation_id
    assert hqla_result.correlation_id == request.correlation_id
