from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.gap.models.gap_value import GapValue


class GapAggregation:
    """Aggregate gap values across dimensions for deterministic reporting."""

    def aggregate(self, gaps: tuple[GapValue, ...], request: ProjectionRequest) -> dict[str, dict[str, Decimal]]:
        if not gaps:
            return {"bucket": {}, "currency": {}, "scenario": {}, "product": {}, "counterparty": {}, "instrument": {}, "portfolio": {}, "business_unit": {}}

        dimensions: dict[str, dict[str, Decimal]] = {
            "bucket": {},
            "currency": {},
            "scenario": {},
            "product": {},
            "counterparty": {},
            "instrument": {},
            "portfolio": {},
            "business_unit": {},
        }
        for gap in sorted(gaps, key=lambda item: (item.period_start, item.period_end, item.currency)):
            dimensions["bucket"][gap.bucket] = dimensions["bucket"].get(gap.bucket, Decimal("0")) + gap.net_gap
            dimensions["currency"][gap.currency] = dimensions["currency"].get(gap.currency, Decimal("0")) + gap.net_gap
            dimensions["scenario"][gap.scenario] = dimensions["scenario"].get(gap.scenario, Decimal("0")) + gap.net_gap
            product_key = request.product_type or "default"
            dimensions["product"][product_key] = dimensions["product"].get(product_key, Decimal("0")) + gap.net_gap
            counterparty_key = request.counterparty or "default"
            dimensions["counterparty"][counterparty_key] = dimensions["counterparty"].get(counterparty_key, Decimal("0")) + gap.net_gap
            instrument_key = request.instrument_id or "default"
            dimensions["instrument"][instrument_key] = dimensions["instrument"].get(instrument_key, Decimal("0")) + gap.net_gap
            portfolio_key = request.portfolio_reference or "default"
            dimensions["portfolio"][portfolio_key] = dimensions["portfolio"].get(portfolio_key, Decimal("0")) + gap.net_gap
            business_unit_key = request.business_unit or "default"
            dimensions["business_unit"][business_unit_key] = dimensions["business_unit"].get(business_unit_key, Decimal("0")) + gap.net_gap
        return dimensions
