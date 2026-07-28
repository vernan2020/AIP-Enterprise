from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from aip.domain.analytics.models.analytics_context import AnalyticsContext
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.policies.base.policy_context import PolicyContext


@dataclass(frozen=True, slots=True)
class RelativeValueRequest:
    """Immutable request for a relative-value evaluation."""

    valuation_date: date
    instrument: FinancialInstrument
    observed_market_price: Decimal
    observed_market_yield: Decimal
    reference_curve: YieldCurve | None = None
    market_snapshot_reference: str | None = None
    pricing_configuration: dict[str, object] = field(default_factory=dict)
    analytics_context: AnalyticsContext | None = None
    policy_context: PolicyContext | None = None
    benchmark_yield: Decimal | None = None
    portfolio_reference: str | None = None
    scoring_configuration: dict[str, object] = field(default_factory=dict)
    recommendation_configuration: dict[str, object] = field(default_factory=dict)
    calculation_timestamp: datetime | None = None
    calculation_identifier: str | None = None

    def __post_init__(self) -> None:
        for value, label in ((self.observed_market_price, "Observed market price"), (self.observed_market_yield, "Observed market yield"), (self.benchmark_yield, "Benchmark yield")):
            if value is None:
                continue
            if not value.is_finite():
                raise ValueError(f"{label} must be a finite decimal")
        if self.observed_market_price <= 0:
            raise ValueError("Observed market price must be positive")
        if self.observed_market_yield < 0:
            raise ValueError("Observed market yield cannot be negative")
