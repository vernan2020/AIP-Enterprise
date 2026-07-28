from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.liquidity.hqla.engine.hqla_engine import HQLAEngine
from aip.domain.liquidity.hqla.enums import HQLAClassification
from aip.domain.liquidity.hqla.exceptions import HQLAProviderError
from aip.domain.liquidity.hqla.models.hqla_request import HQLARequest
from aip.domain.relative_value.providers.hqla_eligibility_provider import HQLAEligibilityProvider


class StubEligibilityProvider(HQLAEligibilityProvider):
    def __init__(self, eligible: bool) -> None:
        self._eligible = eligible

    def is_eligible(self, instrument_id: str) -> bool:
        return self._eligible


class FailingEligibilityProvider(HQLAEligibilityProvider):
    def is_eligible(self, instrument_id: str) -> bool:
        raise RuntimeError("provider failed")


def test_engine_classifies_eligible_assets() -> None:
    request = HQLARequest(
        valuation_date=date(2026, 1, 1),
        instrument_id="bond-001",
        marketability_score=Decimal("0.90"),
        transferability_score=Decimal("0.92"),
        liquidity_quality_score=Decimal("0.91"),
        market_depth_score=Decimal("0.89"),
        price_availability_score=Decimal("0.90"),
        settlement_capability_score=Decimal("0.88"),
    )

    result = HQLAEngine().evaluate(request)

    assert result.classification == HQLAClassification.ELIGIBLE
    assert result.eligible is True
    assert result.score == Decimal("0.90")


def test_engine_classifies_conditionally_eligible_assets_when_information_is_missing() -> None:
    request = HQLARequest(
        valuation_date=date(2026, 1, 1),
        instrument_id="bond-002",
        marketability_score=Decimal("0.92"),
        transferability_score=Decimal("0.90"),
        liquidity_quality_score=Decimal("0.88"),
        market_depth_score=None,
        price_availability_score=Decimal("0.91"),
        settlement_capability_score=Decimal("0.87"),
    )

    result = HQLAEngine().evaluate(request)

    assert result.classification == HQLAClassification.CONDITIONALLY_ELIGIBLE
    assert result.eligible is False
    assert result.analytics["missing_count"] == 1


def test_engine_classifies_ineligible_assets_when_encumbered_or_below_threshold() -> None:
    request = HQLARequest(
        valuation_date=date(2026, 1, 1),
        instrument_id="bond-003",
        marketability_score=Decimal("0.70"),
        transferability_score=Decimal("0.72"),
        liquidity_quality_score=Decimal("0.73"),
        market_depth_score=Decimal("0.74"),
        price_availability_score=Decimal("0.75"),
        settlement_capability_score=Decimal("0.76"),
        encumbered=True,
    )

    result = HQLAEngine().evaluate(request)

    assert result.classification == HQLAClassification.INELIGIBLE
    assert result.reason.lower().startswith("encumbered")


def test_engine_returns_unknown_when_no_assessment_data_is_available() -> None:
    request = HQLARequest(valuation_date=date(2026, 1, 1), instrument_id="bond-004")

    result = HQLAEngine().evaluate(request)

    assert result.classification == HQLAClassification.UNKNOWN
    assert result.eligible is False


def test_provider_failures_raise_domain_exception() -> None:
    request = HQLARequest(
        valuation_date=date(2026, 1, 1),
        instrument_id="bond-005",
        eligibility_provider=FailingEligibilityProvider(),
    )

    with pytest.raises(HQLAProviderError):
        HQLAEngine().evaluate(request)


def test_analytics_and_explanation_are_built_for_results() -> None:
    request = HQLARequest(
        valuation_date=date(2026, 1, 1),
        instrument_id="bond-006",
        marketability_score=Decimal("0.3333333333"),
        transferability_score=None,
        liquidity_quality_score=None,
        market_depth_score=None,
        price_availability_score=None,
        settlement_capability_score=None,
        eligibility_provider=StubEligibilityProvider(True),
    )

    result = HQLAEngine().evaluate(request)

    assert result.analytics["average_score"] == Decimal("0.3333333333")
    assert result.explanation.concise_conclusion
    assert result.explanation.supporting_factors
