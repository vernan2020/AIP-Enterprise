from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.engine.policy_engine import PolicyEngine
from aip.domain.policies.severity.policy_severity import PolicySeverity
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import (
    LiquidityPolicyConfig,
)
from src.extensions.coopealianza.liquidity.configuration.policy_reference_config import (
    PolicyReferenceConfig,
)
from src.extensions.coopealianza.liquidity.exceptions import (
    CoopealianzaLiquidityError,
    InstitutionalConfigurationError,
    InstitutionalPolicyError,
    InstitutionalProviderError,
    PolicyReportError,
)
from src.extensions.coopealianza.liquidity.policies.concentration.issuer_concentration_policy import (
    IssuerConcentrationPolicy,
)
from src.extensions.coopealianza.liquidity.policies.hqla.classification_exclusion_policy import (
    ClassificationExclusionPolicy,
)
from src.extensions.coopealianza.liquidity.policies.hqla.issuer_eligibility_policy import (
    IssuerEligibilityPolicy,
)
from src.extensions.coopealianza.liquidity.policies.hqla.marketability_policy import (
    MarketabilityPolicy,
)
from src.extensions.coopealianza.liquidity.policies.hqla.unencumbered_asset_policy import (
    UnencumberedAssetPolicy,
)
from src.extensions.coopealianza.liquidity.policies.issuer_limits.issuer_limit_policy import (
    IssuerLimitPolicy,
)
from src.extensions.coopealianza.liquidity.policies.liquidity_limits.minimum_liquidity_policy import (
    MinimumLiquidityPolicy,
)
from src.extensions.coopealianza.liquidity.policies.mil.collateral_availability_policy import (
    CollateralAvailabilityPolicy,
)
from src.extensions.coopealianza.liquidity.policies.mil.eligible_issuer_policy import (
    EligibleIssuerPolicy,
)
from src.extensions.coopealianza.liquidity.policies.mil.encumbrance_policy import (
    EncumbrancePolicy,
)
from src.extensions.coopealianza.liquidity.providers.institutional_policy_provider import (
    InstitutionalPolicyProvider,
)
from src.extensions.coopealianza.liquidity.providers.portfolio_asset_provider import (
    PortfolioAssetProvider,
)
from src.extensions.coopealianza.liquidity.reports.liquidity_policy_report_builder import (
    LiquidityPolicyReportBuilder,
)


class DummyPortfolioAssetProvider(PortfolioAssetProvider):
    def get_assets(self, portfolio_reference: str) -> tuple[dict[str, Any], ...]:
        return (
            {
                "asset_id": "asset-1",
                "classification": "V.C",
                "encumbrance_status": "unencumbered",
                "issuer_category": "cooperative",
                "marketability_score": Decimal("0.95"),
                "price_availability_score": Decimal("0.90"),
                "collateral_available": True,
                "operationally_available": True,
                "issuer_class": "AA",
                "current_exposure": Decimal("20"),
                "current_concentration": Decimal("0.12"),
                "liquidity_metric": Decimal("250"),
            },
        )


class FailingPortfolioAssetProvider(PortfolioAssetProvider):
    def get_assets(self, portfolio_reference: str) -> tuple[dict[str, Any], ...]:
        raise RuntimeError("boom")


class DummyInstitutionalPolicyProvider(InstitutionalPolicyProvider):
    def get_policy_data(self, portfolio_reference: str) -> dict[str, Any]:
        return {"institutional_reference": "COOP-001"}


class FailingInstitutionalPolicyProvider(InstitutionalPolicyProvider):
    def get_policy_data(self, portfolio_reference: str) -> dict[str, Any]:
        raise RuntimeError("policy boom")


def make_config(**overrides: Any) -> LiquidityPolicyConfig:
    defaults: dict[str, Any] = {
        "policy_id": "policy-1",
        "version": "1.0",
        "name": "Test Policy",
        "category": "hqla",
        "enabled": True,
        "effective_date": date(2024, 1, 1),
        "expiration_date": date(2030, 1, 1),
        "severity": PolicySeverity.HIGH,
        "issuer_categories": ("cooperative",),
        "instrument_classifications": ("V.C",),
        "excluded_classification_prefixes": ("V.C",),
        "issuer_limit": Decimal("100"),
        "concentration_warning_limit": Decimal("0.10"),
        "concentration_blocking_limit": Decimal("0.20"),
        "minimum_liquidity_warning": Decimal("100"),
        "minimum_liquidity_blocking": Decimal("50"),
        "minimum_marketability_score": Decimal("0.80"),
        "minimum_price_availability_score": Decimal("0.75"),
        "required_marketability_attributes": ("marketability_score", "price_availability_score"),
        "required_encumbrance_status": ("unencumbered",),
        "policy_references": (PolicyReferenceConfig(source="regulation", identifier="REG-1"),),
        "recommended_action": "review",
    }
    defaults.update(overrides)
    return LiquidityPolicyConfig(**defaults)


def test_configuration_loads_and_is_immutable() -> None:
    data = {
        "policy_id": "policy-1",
        "version": "1.0",
        "name": "Unencumbered Asset",
        "category": "hqla",
        "enabled": True,
        "effective_date": "2024-01-01",
        "expiration_date": "2030-01-01",
        "severity": "HIGH",
        "issuer_categories": ["cooperative"],
        "instrument_classifications": ["V.C"],
        "excluded_classification_prefixes": ["V.C"],
        "issuer_limit": "100",
        "concentration_warning_limit": "0.10",
        "concentration_blocking_limit": "0.20",
        "minimum_liquidity_warning": "100",
        "minimum_liquidity_blocking": "50",
        "minimum_marketability_score": "0.80",
        "minimum_price_availability_score": "0.75",
        "required_marketability_attributes": ["marketability_score"],
        "required_encumbrance_status": ["unencumbered"],
        "policy_references": [{"source": "regulation", "identifier": "REG-1"}],
        "recommended_action": "review",
    }
    config = LiquidityPolicyConfig.from_mapping(data)
    assert config.policy_id == "policy-1"
    assert config.severity == PolicySeverity.HIGH
    with pytest.raises(AttributeError):
        config.issuer_categories.append("x")


def test_configuration_rejects_invalid_ranges_and_duplicates() -> None:
    duplicate = [make_config(policy_id="p1"), make_config(policy_id="p1")]
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig.validate_configuration_collection(duplicate)

    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="p2", version="1.0", name="bad", category="hqla", issuer_limit=Decimal("-1"))

    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="p3", version="1.0", name="bad", category="hqla", minimum_marketability_score=Decimal("1.2"))

    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="p4", version="1.0", name="bad", category="hqla", effective_date=date(2024, 2, 1), expiration_date=date(2024, 1, 1))


def test_expired_and_disabled_policies_are_not_applicable() -> None:
    config = make_config(enabled=False)
    policy = UnencumberedAssetPolicy(config)
    result = policy.evaluate(PolicyContext(context_id="ctx-1", timestamp=datetime.now(timezone.utc)))
    assert result.status == "NOT_APPLICABLE"

    expired = make_config(effective_date=date(2020, 1, 1), expiration_date=date(2022, 1, 1))
    expired_policy = UnencumberedAssetPolicy(expired)
    result = expired_policy.evaluate(PolicyContext(context_id="ctx-2", timestamp=datetime.now(timezone.utc)))
    assert result.status == "NOT_APPLICABLE"


def test_unencumbered_asset_policy_passes_and_fails() -> None:
    policy = UnencumberedAssetPolicy(make_config())
    context = PolicyContext(context_id="ctx-3", metadata={"asset": {"encumbrance_status": "unencumbered"}})
    result = policy.evaluate(context)
    assert result.status == "PASSED"

    failing = PolicyContext(context_id="ctx-4", metadata={"asset": {"encumbrance_status": "pledged"}})
    result = policy.evaluate(failing)
    assert result.status == "FAILED"

    warning_context = PolicyContext(context_id="ctx-5", metadata={"asset": {"encumbrance_status": "unknown"}})
    result = policy.evaluate(warning_context)
    assert result.status == "WARNING"


def test_classification_exclusion_policy_supports_multiple_prefixes() -> None:
    policy = ClassificationExclusionPolicy(make_config(excluded_classification_prefixes=("V.C", "A.B")))
    matching = PolicyContext(context_id="ctx-6", metadata={"asset": {"classification": "V.C-TEST"}})
    result = policy.evaluate(matching)
    assert result.status == "FAILED"

    non_matching = PolicyContext(context_id="ctx-7", metadata={"asset": {"classification": "X.Y"}})
    result = policy.evaluate(non_matching)
    assert result.status == "PASSED"


def test_issuer_eligibility_policy_uses_configured_categories() -> None:
    policy = IssuerEligibilityPolicy(make_config(issuer_categories=("cooperative", "public")))
    pass_ctx = PolicyContext(context_id="ctx-8", metadata={"asset": {"issuer_category": "cooperative"}})
    assert policy.evaluate(pass_ctx).status == "PASSED"

    fail_ctx = PolicyContext(context_id="ctx-9", metadata={"asset": {"issuer_category": "private"}})
    assert policy.evaluate(fail_ctx).status == "FAILED"

    na_ctx = PolicyContext(context_id="ctx-10", metadata={"asset": {}})
    assert policy.evaluate(na_ctx).status == "NOT_APPLICABLE"


def test_marketability_policy_requires_attributes_and_price_availability() -> None:
    policy = MarketabilityPolicy(make_config(required_marketability_attributes=("marketability_score", "price_availability_score")))
    good_context = PolicyContext(context_id="ctx-11", metadata={"asset": {"marketability_score": Decimal("0.90"), "price_availability_score": Decimal("0.80")}})
    assert policy.evaluate(good_context).status == "PASSED"

    stale_context = PolicyContext(context_id="ctx-12", metadata={"asset": {"marketability_score": Decimal("0.90"), "price_availability_score": Decimal("0.80"), "price_timestamp": date(2020, 1, 1)}})
    result = policy.evaluate(stale_context)
    assert result.status == "WARNING"

    missing_context = PolicyContext(context_id="ctx-13", metadata={"asset": {"marketability_score": Decimal("0.70")}})
    assert policy.evaluate(missing_context).status == "FAILED"


def test_mil_policies_apply_collateral_and_issuer_rules() -> None:
    collateral_policy = CollateralAvailabilityPolicy(make_config())
    assert collateral_policy.evaluate(PolicyContext(context_id="ctx-14", metadata={"asset": {"collateral_available": True, "operationally_available": True}})).status == "PASSED"
    assert collateral_policy.evaluate(PolicyContext(context_id="ctx-15", metadata={"asset": {"collateral_available": False}})).status == "FAILED"

    eligible_policy = EligibleIssuerPolicy(make_config())
    assert eligible_policy.evaluate(PolicyContext(context_id="ctx-16", metadata={"asset": {"issuer_class": "AA"}})).status == "PASSED"
    assert eligible_policy.evaluate(PolicyContext(context_id="ctx-17", metadata={"asset": {"issuer_class": "BB"}})).status == "FAILED"

    encumbrance_policy = EncumbrancePolicy(make_config())
    assert encumbrance_policy.evaluate(PolicyContext(context_id="ctx-18", metadata={"asset": {"encumbrance_status": "unencumbered"}})).status == "PASSED"
    assert encumbrance_policy.evaluate(PolicyContext(context_id="ctx-19", metadata={"asset": {"encumbrance_status": "encumbered"}})).status == "FAILED"


def test_issuer_limit_policy_uses_warning_and_blocking_thresholds() -> None:
    policy = IssuerLimitPolicy(make_config(issuer_limit=Decimal("100")))
    assert policy.evaluate(PolicyContext(context_id="ctx-20", metadata={"asset": {"current_exposure": Decimal("80")}})).status == "PASSED"
    assert policy.evaluate(PolicyContext(context_id="ctx-21", metadata={"asset": {"current_exposure": Decimal("120")}})).status == "WARNING"
    assert policy.evaluate(PolicyContext(context_id="ctx-22", metadata={"asset": {"current_exposure": Decimal("150")}})).status == "FAILED"


def test_issuer_concentration_policy_uses_warning_and_blocking_thresholds() -> None:
    policy = IssuerConcentrationPolicy(make_config(concentration_warning_limit=Decimal("0.10"), concentration_blocking_limit=Decimal("0.20")))
    assert policy.evaluate(PolicyContext(context_id="ctx-23", metadata={"asset": {"current_concentration": Decimal("0.05")}})).status == "PASSED"
    assert policy.evaluate(PolicyContext(context_id="ctx-24", metadata={"asset": {"current_concentration": Decimal("0.15")}})).status == "WARNING"
    assert policy.evaluate(PolicyContext(context_id="ctx-25", metadata={"asset": {"current_concentration": Decimal("0.25")}})).status == "FAILED"


def test_minimum_liquidity_policy_evaluates_supplied_metric() -> None:
    policy = MinimumLiquidityPolicy(make_config(minimum_liquidity_warning=Decimal("100"), minimum_liquidity_blocking=Decimal("50")))
    assert policy.evaluate(PolicyContext(context_id="ctx-26", metadata={"asset": {"liquidity_metric": Decimal("150")}})).status == "PASSED"
    assert policy.evaluate(PolicyContext(context_id="ctx-27", metadata={"asset": {"liquidity_metric": Decimal("75")}})).status == "WARNING"
    assert policy.evaluate(PolicyContext(context_id="ctx-28", metadata={"asset": {"liquidity_metric": Decimal("40")}})).status == "FAILED"


def test_policy_engine_reuses_existing_abstractions() -> None:
    engine = PolicyEngine()
    policy = UnencumberedAssetPolicy(make_config())
    engine.register(policy)
    result = engine.evaluate(policy, PolicyContext(context_id="ctx-29", metadata={"asset": {"encumbrance_status": "unencumbered"}}))
    assert result.status == "PASSED"


def test_report_builder_orders_and_aggregates() -> None:
    builder = LiquidityPolicyReportBuilder()
    policies = [
        UnencumberedAssetPolicy(make_config(policy_id="p-2", category="hqla", name="Asset 2", priority=2)),
        IssuerEligibilityPolicy(make_config(policy_id="p-1", category="hqla", name="Issuer 1", priority=1)),
    ]
    engine = PolicyEngine()
    for policy in policies:
        engine.register(policy)
    results = engine.evaluate_many(policies, PolicyContext(context_id="ctx-30", metadata={"asset": {"encumbrance_status": "unencumbered", "issuer_category": "cooperative"}}))
    report = builder.build(
        results.results,
        portfolio_reference="portfolio-1",
        policy_configuration_version="v1",
        evaluation_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        asset_id="asset-1",
        policy_context=PolicyContext(context_id="ctx-30", metadata={"asset": {"encumbrance_status": "unencumbered", "issuer_category": "cooperative"}}),
    )
    assert report.total_policies_evaluated == 2
    assert report.passed_count == 2
    assert report.evaluations[0].policy_id == "p-1"


def test_provider_ports_success_empty_malformed_and_failure() -> None:
    provider = DummyPortfolioAssetProvider()
    assets = provider.get_assets("portfolio-1")
    assert assets[0]["asset_id"] == "asset-1"

    class EmptyProvider(PortfolioAssetProvider):
        def get_assets(self, portfolio_reference: str) -> tuple[dict[str, Any], ...]:
            return ()

    assert EmptyProvider().get_assets("p")==()

    class MalformedProvider(PortfolioAssetProvider):
        def get_assets(self, portfolio_reference: str) -> tuple[dict[str, Any], ...]:
            return ({"asset_id": "broken"},)

    with pytest.raises(InstitutionalProviderError):
        LiquidityPolicyReportBuilder().build_provider_assets(MalformedProvider(), "p")

    with pytest.raises(InstitutionalProviderError):
        LiquidityPolicyReportBuilder().build_provider_assets(FailingPortfolioAssetProvider(), "p")

    policy_provider = DummyInstitutionalPolicyProvider()
    assert policy_provider.get_policy_data("p")["institutional_reference"] == "COOP-001"

    with pytest.raises(InstitutionalProviderError):
        LiquidityPolicyReportBuilder().build_provider_policy_data(FailingInstitutionalPolicyProvider(), "p")


def test_extension_exceptions_are_specific() -> None:
    with pytest.raises(CoopealianzaLiquidityError):
        raise CoopealianzaLiquidityError("boom")
    with pytest.raises(InstitutionalConfigurationError):
        raise InstitutionalConfigurationError("cfg")
    with pytest.raises(InstitutionalPolicyError):
        raise InstitutionalPolicyError("policy")
    with pytest.raises(InstitutionalProviderError):
        raise InstitutionalProviderError("provider")
    with pytest.raises(PolicyReportError):
        raise PolicyReportError("report")


def test_decimal_precision_and_context_immutability() -> None:
    policy = MarketabilityPolicy(make_config())
    metadata = {"asset": {"marketability_score": Decimal("0.3333333333"), "price_availability_score": Decimal("0.3333333333")}}
    context = PolicyContext(context_id="ctx-31", metadata=metadata)
    result = policy.evaluate(context)
    assert result.status == "PASSED"
    assert context.metadata is metadata


def test_liquidity_policy_config_covers_validation_and_parsing_paths() -> None:
    mapping = {
        "policy_id": "policy-2",
        "version": "2.0",
        "name": "Config Policy",
        "category": "hqla",
        "enabled": True,
        "effective_date": "2024-01-01",
        "expiration_date": "2024-12-31",
        "severity": "HIGH",
        "issuer_categories": ["cooperative"],
        "instrument_classifications": ["V.C"],
        "excluded_classification_prefixes": ["V.C"],
        "issuer_limit": "100",
        "concentration_warning_limit": "0.10",
        "concentration_blocking_limit": "0.20",
        "minimum_liquidity_warning": "100",
        "minimum_liquidity_blocking": "50",
        "minimum_marketability_score": "0.80",
        "minimum_price_availability_score": "0.75",
        "required_marketability_attributes": ["marketability_score"],
        "required_encumbrance_status": ["unencumbered"],
        "policy_references": [{"source": "regulation", "identifier": "REG-2"}],
        "recommended_action": "review",
        "priority": 3,
    }
    config = LiquidityPolicyConfig.from_mapping(mapping)
    assert config.severity == PolicySeverity.HIGH
    assert config.to_policy_reference()[0].identifier == "REG-2"

    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="", version="1.0", name="bad", category="hqla")
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="p", version="1.0", name="bad", category="hqla", issuer_limit=Decimal("-1"))
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="p", version="1.0", name="bad", category="hqla", minimum_marketability_score=Decimal("1.2"))
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="p", version="1.0", name="bad", category="hqla", effective_date=date(2024, 2, 1), expiration_date=date(2024, 1, 1))
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="p", version="1.0", name="bad", category="hqla", concentration_warning_limit=Decimal("0.20"), concentration_blocking_limit=Decimal("0.10"))
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="p", version="1.0", name="bad", category="hqla", minimum_liquidity_warning=Decimal("50"), minimum_liquidity_blocking=Decimal("100"))
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig(policy_id="p", version="1.0", name="bad", category="hqla", policy_references=(object(),))
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig._parse_date(object())
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig._parse_decimal(object())


def test_configuration_collection_enforces_duplicates_and_reference_identifiers() -> None:
    base = make_config(policy_id="p-1", issuer_categories=("cooperative",))
    duplicate_id = make_config(policy_id="p-1", issuer_categories=("public",))
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig.validate_configuration_collection([base, duplicate_id])

    duplicate_category = make_config(policy_id="p-2", issuer_categories=("cooperative",))
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig.validate_configuration_collection([base, duplicate_category])

    missing_identifier = make_config(policy_id="p-3", policy_references=(PolicyReferenceConfig(source="regulation", identifier=""),))
    with pytest.raises(InstitutionalConfigurationError):
        LiquidityPolicyConfig.validate_configuration_collection([base, missing_identifier])


def test_report_builder_handles_empty_and_malformed_inputs() -> None:
    builder = LiquidityPolicyReportBuilder()
    with pytest.raises(PolicyReportError):
        builder.build(
            (),
            portfolio_reference="portfolio-1",
            policy_configuration_version="v1",
            evaluation_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    evaluations = (
        SimpleNamespace(policy_id="b-policy", context_id="ctx-2", status="FAILED", message="later", references=()),
        SimpleNamespace(policy_id="a-policy", context_id="ctx-1", status="PASSED", message="first", references=()),
    )
    report = builder.build(
        evaluations,
        portfolio_reference="portfolio-1",
        policy_configuration_version="v1",
        evaluation_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        asset_id="asset-1",
    )
    assert [item.policy_id for item in report.evaluations] == ["a-policy", "b-policy"]
    assert report.blocking_failures == ("b-policy",)

    class ListAssetsProvider(PortfolioAssetProvider):
        def get_assets(self, portfolio_reference: str) -> tuple[dict[str, Any], ...]:
            return [{"asset_id": "asset-1", "classification": "V.C"}]  # type: ignore[return-value]

    class MalformedAssetProvider(PortfolioAssetProvider):
        def get_assets(self, portfolio_reference: str) -> tuple[dict[str, Any], ...]:
            return ({"asset_id": "asset-1"},)  # type: ignore[return-value]

    class MissingShapeProvider(PortfolioAssetProvider):
        def get_assets(self, portfolio_reference: str) -> tuple[dict[str, Any], ...]:
            return ({"classification": "V.C"},)  # type: ignore[return-value]

    class InvalidPolicyDataProvider(InstitutionalPolicyProvider):
        def get_policy_data(self, portfolio_reference: str) -> dict[str, Any]:
            return []  # type: ignore[return-value]

    with pytest.raises(InstitutionalProviderError):
        builder.build_provider_assets(ListAssetsProvider(), "p")
    with pytest.raises(InstitutionalProviderError):
        builder.build_provider_assets(MalformedAssetProvider(), "p")
    with pytest.raises(InstitutionalProviderError):
        builder.build_provider_assets(MissingShapeProvider(), "p")
    with pytest.raises(InstitutionalProviderError):
        builder.build_provider_policy_data(InvalidPolicyDataProvider(), "p")

    valid_assets = builder.build_provider_assets(DummyPortfolioAssetProvider(), "portfolio-1")
    assert valid_assets[0]["asset_id"] == "asset-1"
    assert builder.build_provider_policy_data(DummyInstitutionalPolicyProvider(), "portfolio-1")["institutional_reference"] == "COOP-001"


def test_policy_protocols_raise_not_implemented_when_called_directly() -> None:
    class PortfolioProtocolStub(PortfolioAssetProvider):
        def get_assets(self, portfolio_reference: str) -> tuple[dict[str, Any], ...]:
            return super().get_assets(portfolio_reference)

    class PolicyProtocolStub(InstitutionalPolicyProvider):
        def get_policy_data(self, portfolio_reference: str) -> dict[str, Any]:
            return super().get_policy_data(portfolio_reference)

    with pytest.raises(NotImplementedError):
        PortfolioProtocolStub().get_assets("p")
    with pytest.raises(NotImplementedError):
        PolicyProtocolStub().get_policy_data("p")


def test_policies_support_boundary_and_numeric_coercion_paths() -> None:
    issuer_limit_policy = IssuerLimitPolicy(make_config(issuer_limit=Decimal("100")))
    assert issuer_limit_policy.evaluate(PolicyContext(context_id="ctx-32", metadata={"asset": {"current_exposure": Decimal("100")}})).status == "WARNING"
    assert issuer_limit_policy.evaluate(PolicyContext(context_id="ctx-33", metadata={"asset": {"current_exposure": "120"}})).status == "WARNING"
    with pytest.raises(InstitutionalPolicyError):
        issuer_limit_policy.evaluate(PolicyContext(context_id="ctx-34", metadata={"asset": {"current_exposure": object()}}))

    concentration_policy = IssuerConcentrationPolicy(make_config(concentration_warning_limit=Decimal("0.10"), concentration_blocking_limit=Decimal("0.20")))
    assert concentration_policy.evaluate(PolicyContext(context_id="ctx-35", metadata={"asset": {"current_concentration": Decimal("0.10")}})).status == "WARNING"
    assert concentration_policy.evaluate(PolicyContext(context_id="ctx-36", metadata={"asset": {"current_concentration": 0.15}})).status == "WARNING"
    with pytest.raises(InstitutionalPolicyError):
        concentration_policy.evaluate(PolicyContext(context_id="ctx-37", metadata={"asset": {"current_concentration": object()}}))

    minimum_liquidity_policy = MinimumLiquidityPolicy(make_config(minimum_liquidity_warning=Decimal("100"), minimum_liquidity_blocking=Decimal("50")))
    assert minimum_liquidity_policy.evaluate(PolicyContext(context_id="ctx-38", metadata={"asset": {"liquidity_metric": Decimal("100")}})).status == "PASSED"
    assert minimum_liquidity_policy.evaluate(PolicyContext(context_id="ctx-39", metadata={"asset": {"liquidity_metric": 75}})).status == "WARNING"
    assert minimum_liquidity_policy.evaluate(PolicyContext(context_id="ctx-40", metadata={"asset": {"liquidity_metric": "30"}})).status == "FAILED"
    with pytest.raises(InstitutionalPolicyError):
        minimum_liquidity_policy.evaluate(PolicyContext(context_id="ctx-41", metadata={"asset": {"liquidity_metric": object()}}))

    marketability_policy = MarketabilityPolicy(make_config(required_marketability_attributes=("marketability_score", "price_availability_score")))
    assert marketability_policy.evaluate(PolicyContext(context_id="ctx-42", metadata={"asset": {"marketability_score": "0.90", "price_availability_score": Decimal("0.80")}})).status == "PASSED"
    with pytest.raises(InstitutionalPolicyError):
        marketability_policy.evaluate(PolicyContext(context_id="ctx-43", metadata={"asset": {"marketability_score": object(), "price_availability_score": Decimal("0.80")}}))
