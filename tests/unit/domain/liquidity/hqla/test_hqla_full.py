from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

import pytest

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.liquidity.hqla.engine.hqla_engine import HQLAEngine
from aip.domain.liquidity.hqla.engine.hqla_policy_engine import HQLAPolicyEngine
from aip.domain.liquidity.hqla.enums import HQLAClassification
from aip.domain.liquidity.hqla.exceptions import HQLAError, HQLAProviderError
from aip.domain.liquidity.hqla.models.hqla_request import HQLARequest
from aip.domain.liquidity.hqla.models.liquidity_asset import LiquidityAsset
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.base.policy import Policy
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity
from aip.domain.relative_value.providers.hqla_eligibility_provider import HQLAEligibilityProvider


class RecordingProvider(HQLAEligibilityProvider):
    def __init__(self, value: bool) -> None:
        self.value = value

    def is_eligible(self, instrument_id: str) -> bool:
        return self.value


class MarketabilityProviderStub:
    def assess(self, instrument_id: str) -> dict[str, object]:
        return {"marketable": True, "depth": "deep", "price": Decimal("100")}


class EncumbranceProviderStub:
    def assess(self, instrument_id: str) -> dict[str, object]:
        return {"encumbered": False, "evidence": "none"}


class SamplePolicy(Policy):
    def __init__(self, policy_id: str, status: str, enabled: bool = True) -> None:
        super().__init__(policy_id=policy_id, name=policy_id, description="sample", version="1.0", enabled=enabled, severity=PolicySeverity.INFO, category="hqla", reference=PolicyReference(source="test", identifier=policy_id))
        self._status = status

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        return EvaluationResult(
            policy_id=self.policy_id,
            status=self._status,
            message="ok",
            severity=self.severity,
            references=(self.reference,),
            timestamp=date.today(),
            evaluation_duration=None,
            context_id=context.context_id,
        )


class BrokenPolicy(SamplePolicy):
    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        raise RuntimeError("boom")


def test_liquidity_asset_validation() -> None:
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("100"), haircut=Decimal("0"), encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("-1"), haircut=Decimal("0"), encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("NaN"), haircut=Decimal("0"), encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("Infinity"), haircut=Decimal("0"), encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("1"), haircut=Decimal("-0.1"), encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("1"), haircut=Decimal("1.1"), encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("1"), haircut=Decimal("0"), encumbered=False, marketability_indicators="bad")
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("1"), haircut=Decimal("0"), encumbered=False, settlement_indicators="bad")
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("1"), haircut=Decimal("0"), encumbered=False, metadata="bad")
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value="10", haircut=Decimal("0"), encumbered=False)


def test_liquidity_asset_metadata_is_defensively_copied() -> None:
    metadata = {"source": "api"}
    asset = LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("100"), haircut=Decimal("0"), encumbered=False, metadata=metadata)
    metadata["source"] = "changed"
    assert asset.metadata["source"] == "api"


def test_liquidity_asset_exposes_adjusted_value_and_validates_missing_fields() -> None:
    asset = LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("100"), haircut=Decimal("0.25"), encumbered=False)
    assert asset.adjusted_value == Decimal("75")

    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="", issuer="issuer", currency="USD", market_value=Decimal("1"), haircut=Decimal("0"), encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="", currency="USD", market_value=Decimal("1"), haircut=Decimal("0"), encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="", market_value=Decimal("1"), haircut=Decimal("0"), encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("1"), haircut="0", encumbered=False)
    with pytest.raises(HQLAError):
        LiquidityAsset(identifier="x", instrument="bond", issuer="issuer", currency="USD", market_value=Decimal("1"), haircut=Decimal("NaN"), encumbered=False)


def test_hqla_engine_resolves_precedence() -> None:
    request = HQLARequest(valuation_date=date(2026, 1, 1), instrument_id="x", marketability_score=Decimal("0.85"), transferability_score=Decimal("0.9"), liquidity_quality_score=Decimal("0.85"), market_depth_score=Decimal("0.9"), price_availability_score=Decimal("0.85"), settlement_capability_score=Decimal("0.9"), encumbered=True)
    result = HQLAEngine().evaluate(request)
    assert result.classification == HQLAClassification.INELIGIBLE


def test_hqla_engine_uses_unknown_when_no_data() -> None:
    request = HQLARequest(valuation_date=date(2026, 1, 1), instrument_id="x")
    result = HQLAEngine().evaluate(request)
    assert result.classification == HQLAClassification.UNKNOWN


def test_hqla_engine_supports_provider_failure() -> None:
    request = HQLARequest(valuation_date=date(2026, 1, 1), instrument_id="x", eligibility_provider=RecordingProvider(False))
    result = HQLAEngine().evaluate(request)
    assert result.classification == HQLAClassification.INELIGIBLE


class ExplodingProvider(HQLAEligibilityProvider):
    def is_eligible(self, instrument_id: str) -> bool:
        raise RuntimeError("boom")


def test_hqla_engine_translates_provider_exceptions() -> None:
    request = HQLARequest(valuation_date=date(2026, 1, 1), instrument_id="x", eligibility_provider=ExplodingProvider())
    with pytest.raises(HQLAProviderError):
        HQLAEngine().evaluate(request)


def test_explanation_exposes_expected_fields() -> None:
    result = HQLAEngine().evaluate(HQLARequest(valuation_date=date(2026, 1, 1), instrument_id="x", marketability_score=Decimal("0.9"), transferability_score=Decimal("0.9"), liquidity_quality_score=Decimal("0.9"), market_depth_score=Decimal("0.9"), price_availability_score=Decimal("0.9"), settlement_capability_score=Decimal("0.9")))
    assert isinstance(result.explanation, Explanation)
    assert result.explanation.supporting_factors
    assert result.explanation.assumptions == ()
    assert result.explanation.warnings == ()


def test_policy_engine_integration_exposes_policy_references() -> None:
    policy = SamplePolicy("policy-1", "PASSED")
    context = PolicyContext(context_id="ctx")
    result = policy.evaluate(context)
    assert result.status == "PASSED"
    assert result.references


def test_hqla_policy_engine_evaluates_policy_results() -> None:
    policy_engine = HQLAPolicyEngine()
    context = PolicyContext(context_id="ctx")
    results = policy_engine.evaluate((SamplePolicy("policy-1", "PASSED"), SamplePolicy("policy-2", "WARNING")), context)

    assert results.total_score == Decimal("1")
    assert len(results.policy_results) == 2


def test_hqla_engine_respects_policy_warning_and_failure_states() -> None:
    warning_policy = SamplePolicy("warning", "WARNING")
    failed_policy = SamplePolicy("failed", "FAILED")

    warning_result = HQLAEngine().evaluate(
        HQLARequest(
            valuation_date=date(2026, 1, 1),
            instrument_id="x",
            marketability_score=Decimal("0.95"),
            transferability_score=Decimal("0.95"),
            liquidity_quality_score=Decimal("0.95"),
            market_depth_score=Decimal("0.95"),
            price_availability_score=Decimal("0.95"),
            settlement_capability_score=Decimal("0.95"),
            policies=(warning_policy,),
        )
    )
    failed_result = HQLAEngine().evaluate(
        HQLARequest(
            valuation_date=date(2026, 1, 1),
            instrument_id="x",
            marketability_score=Decimal("0.95"),
            transferability_score=Decimal("0.95"),
            liquidity_quality_score=Decimal("0.95"),
            market_depth_score=Decimal("0.95"),
            price_availability_score=Decimal("0.95"),
            settlement_capability_score=Decimal("0.95"),
            policies=(failed_policy,),
        )
    )

    assert warning_result.classification == HQLAClassification.CONDITIONALLY_ELIGIBLE
    assert failed_result.classification == HQLAClassification.NOT_ELIGIBLE
