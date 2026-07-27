from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.pricing.exceptions import PricingError, PricingValidationError
from aip.domain.pricing.models.pricing_request import PricingRequest
from aip.domain.pricing.models.pricing_result import PricingResult
from aip.domain.pricing.services.pricing_service import PricingService


@dataclass(slots=True)
class PricingEngine:
    """Domain service that produces a pricing result for an instrument."""

    pricing_service: PricingService = PricingService()

    def price(self, request: PricingRequest) -> PricingResult:
        if request.valuation_date is None:
            raise PricingValidationError("Valuation date is required")
        if request.instrument is None:
            raise PricingValidationError("Instrument is required")
        if request.market_yield < 0:
            raise PricingValidationError("Market yield cannot be negative")

        try:
            clean_price, dirty_price, accrued_interest, market_value, yield_rate, duration, modified_duration, convexity, dv01, pvbp = self.pricing_service.price(
                request.instrument,
                valuation_date=request.valuation_date,
                market_yield=request.market_yield,
            )
        except PricingError as error:
            raise PricingError(str(error)) from error

        return PricingResult(
            clean_price=clean_price,
            dirty_price=dirty_price,
            accrued_interest=accrued_interest,
            market_value=market_value,
            yield_=yield_rate,
            duration=duration,
            modified_duration=modified_duration,
            convexity=convexity,
            dv01=dv01,
            pvbp=pvbp,
            warnings=(),
            assumptions=(),
        )
