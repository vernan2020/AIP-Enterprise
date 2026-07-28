from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.statistics.descriptive_statistics import DescriptiveStatistics
from aip.domain.liquidity.gap.models.gap_value import GapValue


class GapAnalytics:
    """Provide deterministic analytics from gap values without duplicating formulas."""

    def build(self, gaps: tuple[GapValue, ...]) -> dict[str, dict[str, Decimal]]:
        if not gaps:
            return {
                "concentration": {},
                "distribution": {},
                "percentiles": {},
                "weighted_statistics": {},
                "scenario_comparison": {},
            }

        values = [gap.net_gap for gap in gaps]
        statistics = DescriptiveStatistics(values)
        concentration_total = sum((gap.net_gap for gap in gaps), Decimal("0"))
        percentiles = {
            "p25": statistics.percentile(Decimal("0.25")),
            "p50": statistics.percentile(Decimal("0.5")),
            "p75": statistics.percentile(Decimal("0.75")),
        }
        scenario_totals: dict[str, Decimal] = {}
        for gap in gaps:
            scenario_key = gap.scenario or "base"
            scenario_totals[scenario_key] = scenario_totals.get(scenario_key, Decimal("0")) + gap.net_gap
        return {
            "concentration": {"total": concentration_total},
            "distribution": {"stddev": statistics.standard_deviation()},
            "percentiles": percentiles,
            "weighted_statistics": {"mean": statistics.mean()},
            "scenario_comparison": scenario_totals,
        }
