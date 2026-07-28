from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.application.workflows.liquidity_workflow import LiquidityWorkflow
from aip.application.workflows.relative_value_workflow import RelativeValueWorkflow
from aip.domain.liquidity.cashflow.engine.cashflow_engine import CashFlowEngine
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.gap.engine.gap_engine import GapEngine
from aip.domain.liquidity.gap.models.gap_request import GapRequest
from aip.domain.liquidity.hqla.engine.hqla_engine import HQLAEngine
from aip.domain.liquidity.hqla.models.hqla_request import HQLARequest
from aip.domain.pricing.engine.pricing_engine import PricingEngine
from aip.domain.pricing.models.pricing_request import PricingRequest
from aip.domain.relative_value.engine.relative_value_engine import RelativeValueEngine
from aip.domain.relative_value.models.relative_value_request import RelativeValueRequest
from src.extensions.coopealianza.liquidity.mil.engine.mil_eligibility_engine import MilEligibilityEngine
from src.extensions.coopealianza.liquidity.mil.models.mil_request import MilRequest
from src.extensions.coopealianza.liquidity.stress.engine.stress_engine import StressEngine
from src.extensions.coopealianza.liquidity.stress.models.stress_request import StressRequest


def test_complete_treasury_flow_links_pricing_to_stress(analysis_request, treasury_instrument, yield_curve, mil_asset, mil_config, stress_config) -> None:
    pricing_result = PricingEngine().price(
        PricingRequest(
            valuation_date=analysis_request.valuation_date,
            instrument=treasury_instrument,
            market_yield=analysis_request.market_yield,
        )
    )
    relative_value_result = RelativeValueEngine().evaluate(
        RelativeValueRequest(
            valuation_date=analysis_request.valuation_date,
            instrument=treasury_instrument,
            observed_market_price=analysis_request.market_price or Decimal("1000000"),
            observed_market_yield=analysis_request.market_yield,
            reference_curve=yield_curve,
            benchmark_yield=analysis_request.benchmark_yield,
            portfolio_reference="portfolio-1",
        )
    )
    hqla_result = HQLAEngine().evaluate(
        HQLARequest(
            valuation_date=analysis_request.valuation_date,
            instrument_id=treasury_instrument.isin,
            marketability_score=Decimal("0.9"),
            transferability_score=Decimal("0.9"),
            liquidity_quality_score=Decimal("0.9"),
            market_depth_score=Decimal("0.9"),
            price_availability_score=Decimal("0.9"),
            settlement_capability_score=Decimal("0.9"),
            configuration={"currency": "USD"},
        )
    )
    mil_result = MilEligibilityEngine().evaluate(
        MilRequest(
            portfolio_reference="portfolio-1",
            assets=(mil_asset,),
            configuration=mil_config,
            policy_context={"evaluation_date": date(2026, 1, 1)},
        )
    )

    projection_request = ProjectionRequest(
        valuation_date=analysis_request.valuation_date,
        contractual_cashflows=analysis_request.context["contractual_cashflows"],
        portfolio_reference="portfolio-1",
        currency="USD",
        projection_type="contractual",
    )
    projection_result = CashFlowEngine().project(projection_request)
    gap_result = GapEngine().project(
        GapRequest(
            valuation_date=analysis_request.valuation_date,
            cashflow_request=projection_request,
            currency="USD",
            configuration={"opening_liquidity": Decimal("0")},
        )
    )
    stress_result = StressEngine().evaluate(
        StressRequest(
            portfolio_reference="portfolio-1",
            gap_result=gap_result,
            projection_result=projection_result,
            configuration=stress_config,
        )
    )

    assert pricing_result.market_value == Decimal("1000000")
    assert relative_value_result.instrument_id == treasury_instrument.isin
    assert hqla_result.eligible is True
    assert mil_result.positions[0].eligibility_status.value == "ELIGIBLE"
    assert projection_result.projection_type == "contractual"
    assert gap_result.net_gap >= Decimal("0")
    assert stress_result.total_scenarios == 1
    assert stress_result.summary["max_stressed_gap"] >= gap_result.net_gap
