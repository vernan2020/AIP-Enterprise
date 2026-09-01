from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.liquidity.cashflow.calculators.amortization_projection import AmortizationProjection
from aip.domain.liquidity.cashflow.calculators.behavioral_projection import BehavioralProjection
from aip.domain.liquidity.cashflow.calculators.contractual_projection import ContractualProjection
from aip.domain.liquidity.cashflow.calculators.coupon_projection import CouponProjection
from aip.domain.liquidity.cashflow.calculators.rollover_projection import RolloverProjection
from aip.domain.liquidity.cashflow.engine.aggregation_engine import AggregationEngine
from aip.domain.liquidity.cashflow.engine.cashflow_engine import CashFlowEngine
from aip.domain.liquidity.cashflow.engine.projection_engine import ProjectionEngine
from aip.domain.liquidity.cashflow.exceptions import (
    BehavioralError,
    ProjectionError,
)
from aip.domain.liquidity.cashflow.models.behavioral_assumption import BehavioralAssumption
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.cashflow.providers.behavioral_provider import BehavioralProvider
from aip.domain.liquidity.cashflow.providers.rollover_provider import RolloverProvider
from aip.domain.liquidity.cashflow.providers.scenario_provider import ScenarioProvider


class _StaticProvider(BehavioralProvider, ScenarioProvider, RolloverProvider):
    def get_behavioral_assumptions(
        self, request: ProjectionRequest
    ) -> tuple[BehavioralAssumption, ...]:
        return (
            BehavioralAssumption(
                "partial_renewal", probability=Decimal("0.8"), effect_ratio=Decimal("0.25")
            ),
        )

    def get_scenario(self, request: ProjectionRequest) -> str:
        return "base"

    def get_rollover_rate(self, request: ProjectionRequest) -> Decimal:
        return Decimal("0.5")


def test_contractual_projection_projects_coupon_and_principal() -> None:
    request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=(
            CashFlow(
                payment_date=date(2024, 2, 1),
                amount=Decimal("100"),
                currency="USD",
                cash_flow_type="coupon",
            ),
            CashFlow(
                payment_date=date(2025, 1, 1),
                amount=Decimal("1000"),
                currency="USD",
                cash_flow_type="principal",
            ),
        ),
    )
    result = ContractualProjection().project(request)
    assert len(result) == 2
    assert result[0].cash_flow_type == "coupon"
    assert result[1].amount == Decimal("1000")


def test_behavioral_projection_applies_partial_renewal_and_probability_weight() -> None:
    request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=(
            CashFlow(
                payment_date=date(2024, 2, 1),
                amount=Decimal("100"),
                currency="USD",
                cash_flow_type="coupon",
            ),
        ),
        behavioral_assumptions=(
            BehavioralAssumption(
                "partial_renewal", probability=Decimal("0.8"), effect_ratio=Decimal("0.25")
            ),
        ),
    )
    result = BehavioralProjection().project(
        request,
        [
            ProjectionRequest(
                valuation_date=date(2024, 1, 1),
                contractual_cashflows=request.contractual_cashflows,
                behavioral_assumptions=request.behavioral_assumptions,
            )
        ],
    )
    assert result[0].amount == Decimal("20.0")


def test_rollover_coupon_and_amortization_calculators() -> None:
    assert RolloverProjection().project(Decimal("100"), Decimal("0.25")) == Decimal("25")
    assert CouponProjection().project(Decimal("100"), Decimal("0.05")) == Decimal("5")
    assert AmortizationProjection().project(Decimal("1000"), Decimal("0.1")) == Decimal("100")


def test_aggregation_groups_by_currency_bucket_and_scenario() -> None:
    projected = (
        CashFlow(
            payment_date=date(2024, 2, 1),
            amount=Decimal("100"),
            currency="USD",
            cash_flow_type="coupon",
        ),
    )
    request = ProjectionRequest(valuation_date=date(2024, 1, 1), contractual_cashflows=projected)
    result = AggregationEngine().aggregate(projected, request)
    assert result["currency"]["USD"] == Decimal("100")
    assert result["bucket"]["default"] == Decimal("100")
    assert result["scenario"]["base"] == Decimal("100")


def test_cashflow_engine_builds_explanation_and_projection_type() -> None:
    request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=(
            CashFlow(
                payment_date=date(2024, 2, 1),
                amount=Decimal("100"),
                currency="USD",
                cash_flow_type="coupon",
            ),
        ),
        behavioral_assumptions=(
            BehavioralAssumption(
                "early_withdrawal", probability=Decimal("0.5"), effect_ratio=Decimal("0.2")
            )
        ),
    )
    result = CashFlowEngine().project(request)
    assert result.projection_type == "hybrid"
    assert result.assumptions == ("early_withdrawal",)
    assert result.calculation_path[0] == "contractual"


def test_empty_and_negative_flows_raise_projection_error() -> None:
    with pytest.raises(ProjectionError):
        ContractualProjection().project(
            ProjectionRequest(valuation_date=date(2024, 1, 1), contractual_cashflows=())
        )
    with pytest.raises(ProjectionError):
        ContractualProjection().project(
            ProjectionRequest(
                valuation_date=date(2024, 1, 1),
                contractual_cashflows=(
                    SimpleNamespace(
                        payment_date=date(2024, 2, 1),
                        amount=Decimal("0"),
                        currency="USD",
                        cash_flow_type="coupon",
                    ),
                ),
            )
        )
    with pytest.raises(ProjectionError):
        ContractualProjection().project(
            ProjectionRequest(
                valuation_date=date(2024, 1, 1),
                contractual_cashflows=(
                    SimpleNamespace(
                        payment_date=date(2024, 2, 1),
                        amount=Decimal("-1"),
                        currency="USD",
                        cash_flow_type="coupon",
                    ),
                ),
            )
        )


def test_provider_failures_raise_behavioral_error() -> None:
    class FailingProvider(BehavioralProvider):
        def get_behavioral_assumptions(
            self, request: ProjectionRequest
        ) -> tuple[BehavioralAssumption, ...]:
            raise RuntimeError("boom")

    request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=(),
        behavioral_provider=FailingProvider(),
    )
    with pytest.raises(BehavioralError):
        ProjectionEngine().project(request)


def test_reuse_of_analytics_statistics_and_explainability() -> None:
    request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=(
            CashFlow(
                payment_date=date(2024, 2, 1),
                amount=Decimal("100"),
                currency="USD",
                cash_flow_type="coupon",
            ),
            CashFlow(
                payment_date=date(2024, 3, 1),
                amount=Decimal("200"),
                currency="USD",
                cash_flow_type="coupon",
            ),
            CashFlow(
                payment_date=date(2024, 4, 1),
                amount=Decimal("300"),
                currency="USD",
                cash_flow_type="coupon",
            ),
        ),
    )
    result = CashFlowEngine().project(request)
    assert result.percentiles[0] == Decimal("150")
    assert result.weighted_average == Decimal("200")
