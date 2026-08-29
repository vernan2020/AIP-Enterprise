from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor


class StressAnalytics:
    """Build deterministic explainability for stress evaluation."""

    def __init__(self) -> None:
        self._builder = ExplanationBuilder()

    def build_explanation(self, *, conclusion: str, factors: list[tuple[str, Decimal]], source_references: list[str] | None = None) -> Explanation:
        explanation_factors = [
            ExplanationFactor(name=name, value=value, direction="increase", contribution=value, source_reference=None)
            for name, value in factors
        ]
        return self._builder.build(conclusion, explanation_factors, assumptions=["Existing gap and cashflow projections were reused"], warnings=[], source_references=source_references or [])

    def build_gap_deterioration(self, *, baseline_gap: Decimal, stressed_gap: Decimal) -> Explanation:
        return self.build_explanation(conclusion="Gap deterioration", factors=[("gap_deterioration", stressed_gap - baseline_gap)])

    def build_liquidity_coverage_variation(self, *, baseline_outflow: Decimal, stressed_outflow: Decimal) -> Explanation:
        return self.build_explanation(conclusion="Liquidity coverage variation", factors=[("liquidity_coverage_variation", stressed_outflow - baseline_outflow)])

    def build_collateral_capacity_variation(self, *, baseline_capacity: Decimal, stressed_capacity: Decimal) -> Explanation:
        return self.build_explanation(conclusion="Collateral capacity variation", factors=[("collateral_capacity_variation", baseline_capacity - stressed_capacity)])

    def build_hqla_variation(self, *, baseline_capacity: Decimal, stressed_capacity: Decimal) -> Explanation:
        return self.build_explanation(conclusion="HQLA variation", factors=[("hqla_variation", baseline_capacity - stressed_capacity)])

    def build_issuer_concentration_change(self, *, baseline: Decimal, stressed: Decimal) -> Explanation:
        return self.build_explanation(conclusion="Issuer concentration change", factors=[("issuer_concentration_change", stressed - baseline)])

    def build_currency_concentration_change(self, *, baseline: Decimal, stressed: Decimal) -> Explanation:
        return self.build_explanation(conclusion="Currency concentration change", factors=[("currency_concentration_change", stressed - baseline)])

    def build_resilience_ratio(self, *, baseline_gap: Decimal, stressed_gap: Decimal) -> Explanation:
        ratio = Decimal("1") if baseline_gap == 0 else stressed_gap / baseline_gap
        return self.build_explanation(conclusion="Resilience ratio", factors=[("resilience_ratio", ratio)])

    def build_comparison(self, *, baseline_gap: Decimal, stressed_gap: Decimal, baseline_outflow: Decimal, stressed_outflow: Decimal) -> Explanation:
        return self.build_explanation(conclusion="Scenario comparison", factors=[("gap_deterioration", stressed_gap - baseline_gap), ("liquidity_coverage_variation", stressed_outflow - baseline_outflow)])
