from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.engine.cashflow_engine import CashFlowEngine
from aip.domain.liquidity.gap.engine.gap_engine import GapEngine
from aip.domain.liquidity.gap.models.gap_request import GapRequest
from src.extensions.coopealianza.liquidity.stress.engine.stress_engine import StressEngine
from src.extensions.coopealianza.liquidity.stress.models.stress_request import StressRequest
from src.extensions.coopealianza.liquidity.stress.reports.stress_report_builder import (
    StressReportBuilder,
)


def test_report_consistency_aggregates_stress_output_for_reporting(
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
    report = StressReportBuilder().build(stress_result)

    assert report["calculation_id"] == "stress-portfolio-1"
    assert report["scenario_results"][0]["scenario_name"] == "parallel_shift"
    assert report["policy_references"] == ["STRESS-REF"]
    assert report["warnings"] == ["watch"]
