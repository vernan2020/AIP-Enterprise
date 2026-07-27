from __future__ import annotations

from aip.core.exceptions import ValidationError


class PricingError(ValidationError):
    """Base exception for pricing domain errors."""

    default_code = "PRICING_ERROR"


class PricingValidationError(PricingError):
    """Raised when a pricing request is invalid."""

    default_code = "PRICING_VALIDATION_ERROR"
