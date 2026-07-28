from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.liquidity.cashflow.models.behavioral_assumption import BehavioralAssumption
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.gap.aggregation.gap_aggregation import GapAggregation
from aip.domain.liquidity.gap.analytics.gap_analytics import GapAnalytics
from aip.domain.liquidity.gap.engine.gap_engine import GapEngine
from aip.domain.liquidity.gap.exceptions import AggregationError, CurrencyAggregationError, GapProviderError, LiquidityGapError
from aip.domain.liquidity.gap.models.gap_request import GapRequest
from aip.domain.liquidity.gap.models.gap_value import GapValue
from aip.domain.liquidity.gap.providers.exchange_rate_policy_provider import ExchangeRatePolicyProvider
from aip.domain.liquidity.gap.providers.liquidity_policy_provider import LiquidityPolicyProvider
from aip.domain.liquidity.gap.providers.gap_provider import GapProvider


class _StaticGapProvider(GapProvider):
    def get_projection_request(self, request: GapRequest) -> ProjectionRequest:
        return ProjectionRequest(
            valuation_date=request.valuation_date,
            contractual_cashflows=(
                CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("100"), currency="USD", cash_flow_type="coupon"),
                CashFlow(payment_date=date(2024, 3, 1), amount=Decimal("-40"), currency="USD", cash_flow_type="principal"),
            ),
            business_unit="treasury",
            portfolio_reference="pf-1",
            product_type="loan",
            counterparty="cpty-a",
            instrument_id="inst-1",
            currency="USD",
            scenario_name="base",
        )


class _BrokenGapProvider(GapProvider):
    def get_projection_request(self, request: GapRequest) -> ProjectionRequest:
        raise RuntimeError("boom")


class _RateProvider(ExchangeRatePolicyProvider):
    def get_rate(self, from_currency: str, to_currency: str, valuation_date: date | None = None) -> Decimal:
        return Decimal("1.10")


class _PolicyProvider(LiquidityPolicyProvider):
    def get_policy(self, request: GapRequest) -> dict[str, object]:
        return {"opening_liquidity": Decimal("50"), "bucket_configuration": ((date(2024, 1, 1), date(2024, 2, 15), "short"),)}


def test_net_gap_reconciles_inflows_outflows_and_precision() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(
                CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("100.50"), currency="USD", cash_flow_type="coupon"),
                CashFlow(payment_date=date(2024, 3, 1), amount=Decimal("-40.25"), currency="USD", cash_flow_type="principal"),
            ),
        ),
    )

    result = GapEngine().project(request)

    assert result.gross_inflow == Decimal("100.50")
    assert result.gross_outflow == Decimal("40.25")
    assert result.net_gap == Decimal("60.25")
    assert result.net_gap == result.gross_inflow - result.gross_outflow
    assert result.position == "surplus"


def test_incremental_gap_is_bucket_based_and_deterministic() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(
                CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("30"), currency="USD", cash_flow_type="coupon"),
                CashFlow(payment_date=date(2024, 3, 1), amount=Decimal("-20"), currency="USD", cash_flow_type="principal"),
                CashFlow(payment_date=date(2024, 4, 1), amount=Decimal("10"), currency="USD", cash_flow_type="deposit"),
            ),
        ),
        configuration={"bucket_configuration": ((date(2024, 1, 1), date(2024, 2, 29), "short"), (date(2024, 3, 1), date(2024, 4, 30), "long"))},
    )

    result = GapEngine().project(request)

    assert result.incremental_gap == Decimal("20")
    assert {gap.bucket for gap in result.gaps} == {"short", "long"}
    assert result.gaps[0].incremental_gap == Decimal("30")
    assert result.gaps[1].incremental_gap == Decimal("-20")
    assert result.gaps[2].incremental_gap == Decimal("10")


def test_cumulative_gap_uses_opening_liquidity_and_unordered_input() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(
                CashFlow(payment_date=date(2024, 4, 1), amount=Decimal("-20"), currency="USD", cash_flow_type="loan"),
                CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("30"), currency="USD", cash_flow_type="coupon"),
                CashFlow(payment_date=date(2024, 3, 1), amount=Decimal("-10"), currency="USD", cash_flow_type="principal"),
            ),
        ),
        configuration={"opening_liquidity": Decimal("100")},
    )

    result = GapEngine().project(request)

    assert result.opening_liquidity == Decimal("100")
    assert result.cumulative_gap == Decimal("100")
    assert result.gaps[0].cumulative_gap == Decimal("130")
    assert result.gaps[1].cumulative_gap == Decimal("120")
    assert result.gaps[2].cumulative_gap == Decimal("100")


def test_contractual_gap_uses_cashflow_engine_output() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(
                CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("50"), currency="USD", cash_flow_type="coupon"),
                CashFlow(payment_date=date(2024, 3, 1), amount=Decimal("-10"), currency="USD", cash_flow_type="principal"),
            ),
        ),
    )

    result = GapEngine().project(request)

    assert result.projection_type == "contractual"
    assert result.source_cashflows[0].cash_flow_type == "coupon"


def test_behavioral_gap_preserves_assumptions_and_uses_behavioral_projection() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("20"), currency="USD", cash_flow_type="deposit"),),
            behavioral_assumptions=(BehavioralAssumption(name="renewal", probability=Decimal("0.5"), effect_ratio=Decimal("0.5")),),
            projection_type="behavioral",
        ),
        gap_type="behavioral",
    )

    result = GapEngine().project(request)

    assert result.projection_type == "behavioral"
    assert "renewal" in result.assumptions


def test_scenario_gap_isolated_and_comparison() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("20"), currency="USD", cash_flow_type="deposit"),),
            scenario_name="stress",
            projection_type="scenario",
        ),
        gap_type="scenario",
        configuration={"scenario_comparison": {"stress": Decimal("5")}},
    )

    result = GapEngine().project(request)

    assert result.scenario == "stress"
    assert result.analytics["scenario_comparison"]


def test_bucket_aggregation_rejects_overlapping_configuration() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("10"), currency="USD", cash_flow_type="coupon"),),
        ),
        configuration={"bucket_configuration": ((date(2024, 1, 1), date(2024, 3, 1), "a"), (date(2024, 2, 1), date(2024, 4, 1), "b"))},
    )

    with pytest.raises(AggregationError):
        GapEngine().project(request)


def test_dimensional_aggregation_and_metadata() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("10"), currency="USD", cash_flow_type="coupon"),),
            business_unit="treasury",
            portfolio_reference="pf-1",
            product_type="loan",
            counterparty="cpty-a",
            instrument_id="inst-1",
        ),
    )

    result = GapEngine().project(request)

    assert result.aggregation["business_unit"]["treasury"] == Decimal("10")
    assert result.aggregation["portfolio"]["pf-1"] == Decimal("10")
    assert result.aggregation["currency"]["USD"] == Decimal("10")
    assert result.bucket_assignments == ("treasury",)


def test_multi_currency_requires_policy_or_converts_explicitly() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(
                CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("10"), currency="USD", cash_flow_type="coupon"),
                CashFlow(payment_date=date(2024, 3, 1), amount=Decimal("5"), currency="EUR", cash_flow_type="deposit"),
            ),
        ),
        currency="USD",
    )

    with pytest.raises(CurrencyAggregationError):
        GapEngine().project(request)

    result = GapEngine().project(GapRequest(valuation_date=date(2024, 1, 1), cashflow_request=request.cashflow_request, currency="USD", exchange_rate_policy_provider=_RateProvider()))
    assert result.currency == "USD"


def test_liquidity_position_and_explainability() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(CashFlow(payment_date=date(2024, 2, 1), amount=Decimal("20"), currency="USD", cash_flow_type="coupon"),),
        ),
        configuration={"opening_liquidity": Decimal("10")},
        assumptions=("assumption-a",),
        warnings=("warning-a",),
        references=("ref-a",),
    )

    result = GapEngine().project(request)

    assert result.position == "surplus"
    assert result.explanation is not None
    assert result.explanation.assumptions == ("assumption-a",)
    assert result.explanation.warnings == ("warning-a",)
    assert result.explanation.source_references == ("ref-a",)


def test_gap_analytics_and_providers() -> None:
    gaps = (
        GapValue(period_start=date(2024, 2, 1), period_end=date(2024, 2, 1), net_gap=Decimal("10"), gross_inflow=Decimal("10"), gross_outflow=Decimal("0"), incremental_gap=Decimal("10"), cumulative_gap=Decimal("10"), currency="USD", bucket="short"),
        GapValue(period_start=date(2024, 3, 1), period_end=date(2024, 3, 1), net_gap=Decimal("-5"), gross_inflow=Decimal("0"), gross_outflow=Decimal("5"), incremental_gap=Decimal("-5"), cumulative_gap=Decimal("5"), currency="EUR", bucket="long"),
    )

    analytics = GapAnalytics().build(gaps)
    assert analytics["concentration"]["total"] == Decimal("5")
    assert analytics["percentiles"]["p50"] == Decimal("2.5")
    assert analytics["scenario_comparison"]["base"] == Decimal("5")


def test_provider_failures_translate_to_domain_exceptions() -> None:
    request = GapRequest(valuation_date=date(2024, 1, 1), gap_provider=_BrokenGapProvider())

    with pytest.raises(GapProviderError):
        GapEngine().project(request)


def test_gap_request_requires_valuation_date() -> None:
    with pytest.raises(ValueError):
        GapRequest(valuation_date=None)  # type: ignore[arg-type]
