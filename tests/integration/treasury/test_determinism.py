from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.engine.cashflow_engine import CashFlowEngine
from aip.domain.liquidity.gap.engine.gap_engine import GapEngine
from aip.domain.liquidity.gap.models.gap_request import GapRequest
from src.extensions.coopealianza.liquidity.stress.engine.stress_engine import StressEngine
from src.extensions.coopealianza.liquidity.stress.models.stress_request import StressRequest


def test_deterministic_chain_yields_same_results_for_repeat_runs(projection_request, stress_config) -> None:
    engine = CashFlowEngine()
    gap_engine = GapEngine()
    stress_engine = StressEngine()

    first_projection = engine.project(projection_request)
    first_gap = gap_engine.project(GapRequest(valuation_date=projection_request.valuation_date, cashflow_request=projection_request, currency="USD", configuration={"opening_liquidity": Decimal("0")}))
    first_stress = stress_engine.evaluate(StressRequest(portfolio_reference="portfolio-1", gap_result=first_gap, projection_result=first_projection, configuration=stress_config))

    second_projection = engine.project(projection_request)
    second_gap = gap_engine.project(GapRequest(valuation_date=projection_request.valuation_date, cashflow_request=projection_request, currency="USD", configuration={"opening_liquidity": Decimal("0")}))
    second_stress = stress_engine.evaluate(StressRequest(portfolio_reference="portfolio-1", gap_result=second_gap, projection_result=second_projection, configuration=stress_config))

    assert first_projection.projected_cashflows == second_projection.projected_cashflows
    assert first_gap.net_gap == second_gap.net_gap
    assert first_stress.summary == second_stress.summary
    assert first_stress.scenario_results[0].stressed_gap == second_stress.scenario_results[0].stressed_gap
