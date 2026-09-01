from __future__ import annotations

from decimal import Decimal

from aip.domain.pricing.engine.pricing_engine import PricingEngine
from aip.domain.pricing.models.pricing_request import PricingRequest
from aip.domain.relative_value.engine.relative_value_engine import RelativeValueEngine
from aip.domain.relative_value.models.relative_value_request import RelativeValueRequest


def test_decimal_precision_is_preserved_across_pricing_and_relative_value(
    treasury_instrument, yield_curve, analysis_request
) -> None:
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

    assert isinstance(pricing_result.market_value, Decimal)
    assert isinstance(pricing_result.dirty_price, Decimal)
    assert isinstance(relative_value_result.percentage_price_difference, Decimal)
    assert pricing_result.market_value == Decimal("1000000")
    assert relative_value_result.theoretical_price == pricing_result.market_value + (
        relative_value_result.nominal_spread * Decimal("100000")
    )
