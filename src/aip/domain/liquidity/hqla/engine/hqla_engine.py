from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.hqla.analytics.hqla_analytics import HQLAAnalytics
from aip.domain.liquidity.hqla.engine.hqla_policy_engine import HQLAPolicyEngine
from aip.domain.liquidity.hqla.enums import HQLAClassification
from aip.domain.liquidity.hqla.exceptions import HQLAProviderError
from aip.domain.liquidity.hqla.explainability.hqla_explanation import HQLAExplanation
from aip.domain.liquidity.hqla.models.hqla_request import HQLARequest
from aip.domain.liquidity.hqla.models.hqla_result import HQLAResult
from aip.domain.policies.base.policy_context import PolicyContext


class HQLAEngine:
    """Evaluate whether an instrument qualifies as HQLA."""

    def __init__(self) -> None:
        self._analytics = HQLAAnalytics()
        self._explanation = HQLAExplanation()

    def evaluate(self, request: HQLARequest) -> HQLAResult:
        if request.eligibility_provider is not None:
            try:
                eligible = request.eligibility_provider.is_eligible(request.instrument_id or "")
            except Exception as exc:
                raise HQLAProviderError("HQLA provider failed") from exc
        else:
            eligible = True

        values = (
            request.marketability_score,
            request.transferability_score,
            request.liquidity_quality_score,
            request.market_depth_score,
            request.price_availability_score,
            request.settlement_capability_score,
        )
        missing_count = sum(1 for value in values if value is None)
        available_values = [value for value in values if value is not None]
        if available_values:
            score = sum(available_values, Decimal("0")) / Decimal(len(available_values))
        else:
            score = Decimal("0")

        policy_context = PolicyContext(context_id=f"hqla-{request.instrument_id or 'asset'}")
        policy_results = None
        if request.policies:
            policy_results = HQLAPolicyEngine().evaluate(request.policies, policy_context)
            if any(result.status == "FAILED" for result in policy_results.policy_results):
                classification = HQLAClassification.NOT_ELIGIBLE
                reason = "One or more policies blocked HQLA eligibility"
                eligible_flag = False
            elif any(result.status == "WARNING" for result in policy_results.policy_results):
                classification = HQLAClassification.CONDITIONALLY_ELIGIBLE
                reason = "One or more policies emitted warnings"
                eligible_flag = False
            else:
                classification = None
        else:
            classification = None

        if classification is None and request.encumbered:
            classification = HQLAClassification.NOT_ELIGIBLE
            reason = "Encumbered assets are not eligible for HQLA classification"
            eligible_flag = False
        elif classification is None and not eligible:
            classification = HQLAClassification.NOT_ELIGIBLE
            reason = "Instrument is not eligible according to the configured policy"
            eligible_flag = False
        elif classification is None and not available_values:
            classification = HQLAClassification.UNKNOWN
            reason = "No HQLA assessment data was provided"
            eligible_flag = False
        elif classification is None and missing_count > 0:
            classification = HQLAClassification.CONDITIONALLY_ELIGIBLE
            reason = "Insufficient scoring information for full eligibility"
            eligible_flag = False
        elif classification is None and score >= Decimal("0.8"):
            classification = HQLAClassification.ELIGIBLE
            reason = "Asset meets the high-quality liquid asset threshold"
            eligible_flag = True
        elif classification is None:
            classification = HQLAClassification.NOT_ELIGIBLE
            reason = "Asset score is below the minimum HQLA threshold"
            eligible_flag = False

        analytics = self._analytics.build(values, missing_count)
        explanation = self._explanation.build(
            classification.value,
            score,
            reason,
            request.assumptions,
            request.warnings,
            request.references,
        )
        return HQLAResult(
            valuation_date=request.valuation_date,
            instrument_id=request.instrument_id,
            classification=classification,
            eligible=eligible_flag,
            score=score,
            reason=reason,
            analytics=analytics,
            explanation=explanation,
            currency=request.configuration.get("currency", "USD") if isinstance(request.configuration.get("currency"), str) else "USD",
        )
