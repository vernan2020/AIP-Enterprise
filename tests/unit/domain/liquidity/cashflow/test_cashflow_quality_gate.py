from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule
from aip.domain.liquidity.cashflow.calculators.amortization_projection import AmortizationProjection
from aip.domain.liquidity.cashflow.calculators.behavioral_projection import BehavioralProjection
from aip.domain.liquidity.cashflow.calculators.contractual_projection import ContractualProjection
from aip.domain.liquidity.cashflow.calculators.coupon_projection import CouponProjection
from aip.domain.liquidity.cashflow.calculators.rollover_projection import RolloverProjection
from aip.domain.liquidity.cashflow.engine.aggregation_engine import AggregationEngine
from aip.domain.liquidity.cashflow.engine.cashflow_engine import CashFlowEngine
from aip.domain.liquidity.cashflow.engine.projection_engine import ProjectionEngine
from aip.domain.liquidity.cashflow.exceptions import (
    AggregationError,
    BehavioralError,
    ProjectionError,
    ScenarioError,
)
from aip.domain.liquidity.cashflow.models.behavioral_assumption import BehavioralAssumption
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.cashflow.models.projection_result import ProjectionResult
from aip.domain.liquidity.cashflow.providers.behavioral_provider import BehavioralProvider
from aip.domain.liquidity.cashflow.providers.scenario_provider import ScenarioProvider


class _StaticBehavioralProvider(BehavioralProvider):
    def get_behavioral_assumptions(
        self, request: ProjectionRequest
    ) -> tuple[BehavioralAssumption, ...]:
        return (
            BehavioralAssumption(
                "partial_renewal", probability=Decimal("0.8"), effect_ratio=Decimal("0.25")
            ),
        )


class _StaticScenarioProvider(ScenarioProvider):
    def get_scenario(self, request: ProjectionRequest) -> str:
        return "stress"


class _BrokenScenarioProvider(ScenarioProvider):
    def get_scenario(self, request: ProjectionRequest) -> str:
        raise RuntimeError("boom")


class _BrokenBehavioralProvider(BehavioralProvider):
    def get_behavioral_assumptions(
        self, request: ProjectionRequest
    ) -> tuple[BehavioralAssumption, ...]:
        raise RuntimeError("boom")


def test_contractual_projection_filters_pre_valuation_and_preserves_decimal_precision() -> None:
    valuation_date = date(2024, 1, 1)
    request = ProjectionRequest(
        valuation_date=valuation_date,
        contractual_cashflows=(
            CashFlow(
                payment_date=date(2023, 12, 31),
                amount=Decimal("100"),
                currency="USD",
                cash_flow_type="principal",
            ),
            CashFlow(
                payment_date=valuation_date,
                amount=Decimal("100.50"),
                currency="USD",
                cash_flow_type="coupon",
            ),
            CashFlow(
                payment_date=date(2024, 2, 1),
                amount=Decimal("1000.25"),
                currency="USD",
                cash_flow_type="principal",
            ),
        ),
    )

    result = ContractualProjection().project(request)

    assert len(result) == 2
    assert result[0].amount == Decimal("100.50")
    assert result[1].amount == Decimal("1000.25")
    assert result[1].cash_flow_type == "principal"


def test_contractual_projection_rejects_empty_and_malformed_schedules() -> None:
    with pytest.raises(ProjectionError):
        ContractualProjection().project(
            ProjectionRequest(valuation_date=date(2024, 1, 1), contractual_cashflows=())
        )

    malformed = (
        SimpleNamespace(
            payment_date=None, amount=Decimal("100"), currency="USD", cash_flow_type="coupon"
        ),
        SimpleNamespace(
            payment_date=date(2024, 2, 1),
            amount=Decimal("0"),
            currency="USD",
            cash_flow_type="coupon",
        ),
        SimpleNamespace(
            payment_date=date(2024, 2, 1),
            amount=Decimal("-1"),
            currency="USD",
            cash_flow_type="coupon",
        ),
    )
    with pytest.raises(ProjectionError):
        ContractualProjection().project(
            ProjectionRequest(valuation_date=date(2024, 1, 1), contractual_cashflows=malformed)
        )


def test_behavioral_projection_respects_probability_boundaries_and_conflicting_assumptions() -> (
    None
):
    contractual = (
        CashFlow(
            payment_date=date(2024, 2, 1),
            amount=Decimal("100"),
            currency="USD",
            cash_flow_type="principal",
        ),
    )
    request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=contractual,
        behavioral_assumptions=(
            BehavioralAssumption(
                "zero_probability", probability=Decimal("0"), effect_ratio=Decimal("0.5")
            ),
            BehavioralAssumption(
                "full_probability", probability=Decimal("1"), effect_ratio=Decimal("0.5")
            ),
        ),
    )

    result = BehavioralProjection().project(request, [contractual])

    assert len(result) == 2
    assert result[0].amount == Decimal("0")
    assert result[1].amount == Decimal("50")

    with pytest.raises(BehavioralError):
        BehavioralProjection().project(
            ProjectionRequest(
                valuation_date=date(2024, 1, 1),
                contractual_cashflows=contractual,
                behavioral_assumptions=(
                    BehavioralAssumption(
                        "duplicate", probability=Decimal("0.5"), effect_ratio=Decimal("0.25")
                    ),
                    BehavioralAssumption(
                        "duplicate", probability=Decimal("0.6"), effect_ratio=Decimal("0.25")
                    ),
                ),
            ),
            [contractual],
        )


def test_rollover_projection_handles_rates_and_domain_errors() -> None:
    assert RolloverProjection().project(Decimal("100"), Decimal("0.25")) == Decimal("25")
    assert RolloverProjection().project(Decimal("100"), Decimal("1")) == Decimal("100")
    assert RolloverProjection().project(Decimal("100"), Decimal("0")) == Decimal("0")

    for invalid_rate in (Decimal("-0.01"), Decimal("1.01")):
        with pytest.raises(ProjectionError):
            RolloverProjection().project(Decimal("100"), invalid_rate)


def test_coupon_projection_uses_coupon_schedule_and_zero_coupon_behavior() -> None:
    schedule = CouponSchedule.from_frequency(
        issue_date=date(2024, 1, 1),
        maturity_date=date(2024, 12, 1),
        payment_frequency=PaymentFrequency.ANNUAL,
        coupon_rate=Decimal("0.05"),
        nominal_value=Decimal("1000"),
    )
    instrument = SimpleNamespace(
        coupon_schedule=schedule, coupon_rate=Decimal("0.05"), coupon_type="fixed"
    )

    assert CouponProjection().project(instrument) == Decimal("1100.00")

    zero_coupon = SimpleNamespace(
        coupon_schedule=CouponSchedule(), coupon_rate=Decimal("0"), coupon_type="zero"
    )
    assert CouponProjection().project(zero_coupon) == Decimal("0")

    with pytest.raises(ProjectionError):
        CouponProjection().project(
            SimpleNamespace(coupon_schedule=None, coupon_rate=Decimal("0.05"), coupon_type="fixed")
        )

    with pytest.raises(ProjectionError):
        CouponProjection().project(
            SimpleNamespace(
                coupon_schedule=CouponSchedule(),
                coupon_rate=Decimal("0.05"),
                coupon_type="unsupported",
            )
        )


def test_amortization_projection_rejects_invalid_and_excessive_values() -> None:
    assert AmortizationProjection().project(Decimal("100"), Decimal("0.25")) == Decimal("25")
    assert AmortizationProjection().project(Decimal("0"), Decimal("0.25")) == Decimal("0")

    with pytest.raises(ProjectionError):
        AmortizationProjection().project(Decimal("100"), Decimal("2"))
    with pytest.raises(ProjectionError):
        AmortizationProjection().project(Decimal("-1"), Decimal("0.25"))


def test_cashflow_engine_reports_hybrid_and_scenario_projection_types() -> None:
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
        scenario_provider=_StaticScenarioProvider(),
    )
    result = CashFlowEngine().project(request)
    assert result.projection_type == "hybrid"
    assert result.scenario == "stress"
    assert result.assumptions == ("early_withdrawal",)

    contractual_request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=(
            CashFlow(
                payment_date=date(2024, 2, 1),
                amount=Decimal("100"),
                currency="USD",
                cash_flow_type="coupon",
            ),
        ),
    )
    contractual_result = CashFlowEngine().project(contractual_request)
    assert contractual_result.projection_type == "contractual"


def test_aggregation_engine_supports_dimensions_and_deterministic_ordering() -> None:
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
        business_unit="treasury",
        product_type="loan",
        counterparty="cpty-a",
        instrument_id="inst-1",
        portfolio_reference="pf-1",
    )
    projected = (
        CashFlow(
            payment_date=date(2024, 2, 1),
            amount=Decimal("100"),
            currency="USD",
            cash_flow_type="coupon",
        ),
        CashFlow(
            payment_date=date(2024, 3, 1),
            amount=Decimal("50"),
            currency="EUR",
            cash_flow_type="principal",
        ),
    )

    result = AggregationEngine().aggregate(projected, request)

    assert result["bucket"]["treasury"] == Decimal("150")
    assert result["currency"]["USD"] == Decimal("100")
    assert result["currency"]["EUR"] == Decimal("50")
    assert result["product"]["loan"] == Decimal("150")
    assert result["counterparty"]["cpty-a"] == Decimal("150")
    assert result["instrument"]["inst-1"] == Decimal("150")
    assert result["portfolio"]["pf-1"] == Decimal("150")
    assert result["business_unit"]["treasury"] == Decimal("150")

    with pytest.raises(AggregationError):
        AggregationEngine().aggregate((), request)


def test_projection_request_and_result_validation_for_scenario_mode() -> None:
    with pytest.raises(ValueError):
        ProjectionRequest(valuation_date=None)

    with pytest.raises(ValueError):
        ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            projection_type="SCENARIO",
            scenario_name=None,
            scenario_provider=None,
        )

    result = ProjectionResult(projection_type="scenario", projected_cashflows=())
    assert result.projection_type == "scenario"


def test_provider_ports_translate_failures_to_domain_exceptions() -> None:
    request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=(),
        behavioral_provider=_BrokenBehavioralProvider(),
    )
    with pytest.raises(BehavioralError):
        ProjectionEngine().project(request)

    scenario_request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=(),
        scenario_provider=_BrokenScenarioProvider(),
    )
    with pytest.raises(ScenarioError):
        CashFlowEngine().project(scenario_request)

    provider_request = ProjectionRequest(
        valuation_date=date(2024, 1, 1),
        contractual_cashflows=(
            CashFlow(
                payment_date=date(2024, 2, 1),
                amount=Decimal("100"),
                currency="USD",
                cash_flow_type="coupon",
            ),
        ),
        behavioral_provider=_BrokenBehavioralProvider(),
    )
    with pytest.raises(BehavioralError):
        ProjectionEngine().project(provider_request)


def test_behavioral_projection_handles_empty_and_single_parent_results() -> None:
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
            )
        ),
    )

    with pytest.raises(ProjectionError):
        BehavioralProjection().project(request, [])

    single_result = BehavioralProjection().project(
        request,
        [
            SimpleNamespace(
                payment_date=date(2024, 2, 1),
                amount=Decimal("100"),
                currency="USD",
                cash_flow_type="coupon",
                bucket="default",
            )
        ],
    )
    assert single_result[0].amount == Decimal("20")


def test_behavioral_assumption_and_request_validation_raise_domain_errors() -> None:
    with pytest.raises(ValueError):
        BehavioralAssumption("", probability=Decimal("0.5"), effect_ratio=Decimal("0.25"))

    with pytest.raises(ValueError):
        BehavioralAssumption("bad", probability=Decimal("-0.1"), effect_ratio=Decimal("0.25"))

    with pytest.raises(ValueError):
        BehavioralAssumption("bad", probability=Decimal("0.5"), effect_ratio=Decimal("1.1"))

    assert (
        ProjectionRequest(
            valuation_date=date(2024, 1, 1), behavioral_assumptions=None
        ).behavioral_assumptions
        == ()
    )
    with pytest.raises(ValueError):
        ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            projection_type="SCENARIO",
            scenario_name=None,
            scenario_provider=None,
        )


def test_calculators_raise_domain_errors_for_edge_cases() -> None:
    with pytest.raises(ProjectionError):
        RolloverProjection().project(Decimal("-1"), Decimal("0.25"))
    with pytest.raises(ProjectionError):
        AmortizationProjection().project(Decimal("100"), Decimal("-0.25"))
    with pytest.raises(ProjectionError):
        CouponProjection().project(Decimal("100"), None)
    with pytest.raises(ProjectionError):
        CouponProjection().project(
            SimpleNamespace(coupon_schedule=None, coupon_rate=Decimal("0.05"), coupon_type="fixed")
        )
    with pytest.raises(ProjectionError):
        ContractualProjection().project(
            ProjectionRequest(
                valuation_date=date(2024, 1, 1),
                contractual_cashflows=(
                    SimpleNamespace(
                        payment_date=date(2024, 2, 1),
                        amount=None,
                        currency="USD",
                        cash_flow_type="coupon",
                    ),
                ),
            )
        )


def test_projection_engine_translates_provider_and_behavioral_failures() -> None:
    class _ExplodingContractualProjection:
        def project(self, request: ProjectionRequest) -> tuple[CashFlow, ...]:
            raise RuntimeError("boom")

    engine = ProjectionEngine()
    engine._contractual_projection = _ExplodingContractualProjection()
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
        behavioral_provider=_StaticBehavioralProvider(),
    )
    with pytest.raises(BehavioralError):
        engine.project(request)

    class _ExplodingBehavioralProjection:
        def project(
            self, request: ProjectionRequest, parent_results: list[object] | None = None
        ) -> tuple[CashFlow, ...]:
            raise RuntimeError("boom")

    engine = ProjectionEngine()
    engine._behavioral_projection = _ExplodingBehavioralProjection()
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
            )
        ),
    )
    with pytest.raises(BehavioralError):
        engine.project(request)


def test_explainability_captures_assumptions_warnings_and_references() -> None:
    result = CashFlowEngine().project(
        ProjectionRequest(
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
                )
            ),
            warnings=("sensitivity",),
            references=("ref-1",),
        )
    )

    assert result.factors
    assert result.assumptions == ("partial_renewal",)
    assert result.warnings == ("sensitivity",)
    assert result.references == ("ref-1",)
