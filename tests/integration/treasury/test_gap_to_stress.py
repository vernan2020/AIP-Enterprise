from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.engine.cashflow_engine import CashFlowEngine
from aip.domain.liquidity.gap.engine.gap_engine import GapEngine
from aip.domain.liquidity.gap.models.gap_request import GapRequest
from src.extensions.coopealianza.liquidity.stress.engine.stress_engine import StressEngine
from src.extensions.coopealianza.liquidity.stress.models.stress_request import StressRequest


def test_gap_and_stress_chain_preserve_deterministic_ordering(
    projection_request, stress_config
) -> None:
    projection_result = CashFlowEngine().project(projection_request)
    gap_result = GapEngine().project(
        GapRequest(
            valuation_date=projection_request.valuation_date,
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

    assert (
        projection_result.projected_cashflows[0].payment_date
        < projection_result.projected_cashflows[1].payment_date
    )
    assert gap_result.net_gap == Decimal("800000")
    assert stress_result.total_scenarios == 1
    assert stress_result.scenario_results[0].scenario_name == "parallel_shift"
    assert stress_result.summary["max_stressed_gap"] >= gap_result.net_gap
    assert stress_result.policy_references == ("STRESS-REF",)
