from __future__ import annotations

import pytest

from aip.domain.pricing.engine.pricing_engine import PricingEngine
from aip.domain.pricing.exceptions import PricingValidationError
from aip.domain.pricing.models.pricing_request import PricingRequest
from aip.domain.relative_value.engine.relative_value_engine import RelativeValueEngine
from aip.domain.relative_value.exceptions import CurveNotAvailableError
from aip.domain.relative_value.models.relative_value_request import RelativeValueRequest


def test_exception_propagation_for_invalid_pricing_and_relative_value_inputs(
    treasury_instrument, analysis_request
) -> None:
    with pytest.raises(PricingValidationError):
        PricingEngine().price(
            PricingRequest(
                valuation_date=analysis_request.valuation_date,
                instrument=None,  # type: ignore[arg-type]
                market_yield=analysis_request.market_yield,
            )
        )

    with pytest.raises(CurveNotAvailableError):
        RelativeValueEngine().evaluate(
            RelativeValueRequest(
                valuation_date=analysis_request.valuation_date,
                instrument=treasury_instrument,
                observed_market_price=analysis_request.market_price or 1000000,
                observed_market_yield=analysis_request.market_yield,
                reference_curve=None,
                benchmark_yield=analysis_request.benchmark_yield,
                portfolio_reference="portfolio-1",
            )
        )
