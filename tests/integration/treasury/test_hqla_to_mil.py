from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.liquidity.hqla.engine.hqla_engine import HQLAEngine
from aip.domain.liquidity.hqla.models.hqla_request import HQLARequest
from src.extensions.coopealianza.liquidity.mil.engine.mil_eligibility_engine import MilEligibilityEngine
from src.extensions.coopealianza.liquidity.mil.models.mil_request import MilRequest


def test_hqla_and_mil_results_are_explainable_and_policy_aware(treasury_instrument, mil_asset, mil_config) -> None:
    hqla_result = HQLAEngine().evaluate(
        HQLARequest(
            valuation_date=date(2026, 1, 1),
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

    assert hqla_result.eligible is True
    assert hqla_result.classification.value == "eligible"
    assert mil_result.policy_references == ("MIL-REF",)
    assert mil_result.capacity.total_potential_collateral_capacity >= Decimal("0")
    assert mil_result.positions[0].eligibility_status.value == "ELIGIBLE"
