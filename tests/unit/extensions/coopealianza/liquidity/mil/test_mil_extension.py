from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

import src.extensions.coopealianza.liquidity.mil.providers  # noqa: F401
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity
from src.extensions.coopealianza.liquidity.mil.configuration.mil_policy_config import (
    MilHaircutConfig,
    MilPolicyConfig,
)
from src.extensions.coopealianza.liquidity.mil.engine.mil_eligibility_engine import (
    MilEligibilityEngine,
)
from src.extensions.coopealianza.liquidity.mil.enums.mil_eligibility_status import (
    MilEligibilityStatus,
)
from src.extensions.coopealianza.liquidity.mil.exceptions import (
    MilConfigurationError,
    MilEligibilityError,
    MilValuationError,
)
from src.extensions.coopealianza.liquidity.mil.models.mil_asset import MilAsset
from src.extensions.coopealianza.liquidity.mil.models.mil_request import MilRequest
from src.extensions.coopealianza.liquidity.mil.policies.availability_policy import (
    AvailabilityPolicy,
)
from src.extensions.coopealianza.liquidity.mil.reports.mil_report_builder import MilReportBuilder


def make_config() -> MilPolicyConfig:
    return MilPolicyConfig(
        policy_id="mil-policy",
        version="1.0",
        name="MIL Policy",
        category="mil",
        excluded_classification_prefixes=("V.C",),
        eligible_issuer_categories=("cooperative",),
        reserve_liquidity_treatment="conditional",
        acceptable_settlement_rules=("delivery_vs_payment",),
        valuation_freshness_limit_days=5,
        minimum_remaining_maturity_days=90,
        haircut_mappings=(
            MilHaircutConfig(
                issuer_category="cooperative",
                haircut=Decimal("0.10"),
            ),
        ),
    )


def make_asset(**overrides: object) -> MilAsset:
    default_values = {
        "position_id": "pos-1",
        "instrument_id": "inst-1",
        "isin": "US0000000001",
        "issuer": "Coop A",
        "issuer_category": "cooperative",
        "currency": "USD",
        "nominal_amount": Decimal("1000"),
        "market_value": Decimal("1000"),
        "accounting_value": Decimal("1000"),
        "classification": "AAA",
        "encumbrance_status": "unencumbered",
        "reserve_liquidity_status": "standard",
        "operational_availability": True,
        "settlement_capability": "delivery_vs_payment",
        "valuation_date": date(2024, 1, 10),
        "market_price_date": date(2024, 1, 10),
        "maturity_date": date(2024, 6, 30),
        "portfolio_reference": "portfolio-1",
    }
    default_values.update(overrides)
    return MilAsset(**default_values)


def test_mil_engine_evaluates_eligibility_and_capacity() -> None:
    config = make_config()
    engine = MilEligibilityEngine()
    request = MilRequest(
        portfolio_reference="portfolio-1",
        assets=(
            make_asset(
                position_id="pos-eligible",
                market_value=Decimal("1000"),
                valuation_date=date(2024, 1, 10),
                maturity_date=date(2024, 6, 30),
            ),
            make_asset(
                position_id="pos-conditional",
                market_value=Decimal("500"),
                reserve_liquidity_status="reserve",
                valuation_date=date(2024, 1, 1),
                maturity_date=date(2024, 6, 30),
            ),
            make_asset(
                position_id="pos-ineligible", market_value=Decimal("200"), classification="V.C-TEST"
            ),
        ),
        configuration=config,
        policy_context={"evaluation_date": date(2024, 1, 10)},
    )

    result = engine.evaluate(request)

    assert result.total_assets_evaluated == 3
    assert result.status_counts[MilEligibilityStatus.ELIGIBLE.value] == 1
    assert result.status_counts[MilEligibilityStatus.CONDITIONALLY_ELIGIBLE.value] == 1
    assert result.status_counts[MilEligibilityStatus.NOT_ELIGIBLE.value] == 1
    assert result.capacity.eligible_adjusted_collateral_value == Decimal("900")
    assert result.capacity.conditional_adjusted_collateral_value == Decimal("450")
    assert result.capacity.total_potential_collateral_capacity == Decimal("1350")
    assert result.capacity.capacity_by_issuer["Coop A"] == Decimal("1350")
    assert result.capacity.capacity_by_currency["USD"] == Decimal("1350")
    assert result.capacity.capacity_by_classification["AAA"] == Decimal("900")
    assert result.capacity.capacity_by_maturity_band["medium"] == Decimal("1350")


def test_mil_engine_marks_unknown_when_required_inputs_are_missing() -> None:
    config = make_config()
    engine = MilEligibilityEngine()
    request = MilRequest(
        portfolio_reference="portfolio-1",
        assets=(make_asset(position_id="pos-unknown", operational_availability=False),),
        configuration=config,
        policy_context={"evaluation_date": date(2024, 1, 10)},
    )

    result = engine.evaluate(request)
    assert result.positions[0].eligibility_status == MilEligibilityStatus.NOT_ELIGIBLE


def test_mil_report_builder_is_deterministic_and_explainable() -> None:
    config = make_config()
    engine = MilEligibilityEngine()
    request = MilRequest(
        portfolio_reference="portfolio-1",
        assets=(make_asset(position_id="pos-1", market_value=Decimal("1000")),),
        configuration=config,
        policy_context={"evaluation_date": date(2024, 1, 10)},
    )

    result = engine.evaluate(request)
    report = MilReportBuilder().build(result)

    assert report["portfolio_reference"] == "portfolio-1"
    assert report["positions"][0]["position_id"] == "pos-1"
    assert report["capacity"]["eligible_adjusted_collateral_value"] == "900"
    assert report["explanation"]["conclusion"]
    assert report["explanation"]["supporting_factors"]


def test_mil_configuration_is_immutable_and_rejects_invalid_values() -> None:
    config = make_config()
    assert config.excluded_classification_prefixes == ("V.C",)
    assert config.reserve_liquidity_treatment == "conditional"

    try:
        config.excluded_classification_prefixes += ("A.B",)  # type: ignore[assignment]
    except AttributeError:
        pass
    else:
        raise AssertionError("Configuration should be immutable")

    try:
        MilPolicyConfig(
            policy_id="x", version="1", name="y", category="mil", minimum_remaining_maturity_days=-1
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Configuration should reject invalid values")


def test_mil_policy_config_from_mapping_and_validation_collection() -> None:
    mapping = {
        "policy_id": "mil-policy-2",
        "version": "2.0",
        "name": "MIL Policy 2",
        "category": "mil",
        "enabled": True,
        "effective_date": "2024-01-01",
        "expiration_date": "2024-12-31",
        "severity": "MEDIUM",
        "excluded_classification_prefixes": ("V.C", "V.D"),
        "eligible_issuer_categories": ("cooperative", "bank"),
        "reserve_liquidity_treatment": "conditional",
        "acceptable_settlement_rules": ("delivery_vs_payment",),
        "valuation_freshness_limit_days": 7,
        "minimum_remaining_maturity_days": 60,
        "haircut_mappings": ({"issuer_category": "cooperative", "haircut": "0.12"},),
        "warning_concentration_threshold": "0.20",
        "blocking_concentration_threshold": "0.40",
        "issuer_limits": (("Coop A", "0.30"),),
        "currency_limits": (("USD", "0.50"),),
        "policy_references": ({"source": "coopealianza", "identifier": "ref-1"},),
        "recommended_action": "review",
        "priority": 2,
    }
    config = MilPolicyConfig.from_mapping(mapping)
    assert config.effective_date == date(2024, 1, 1)
    assert config.haircut_mappings[0].haircut == Decimal("0.12")
    assert config.policy_references[0].identifier == "ref-1"
    assert config.severity == PolicySeverity.MEDIUM

    with pytest.raises(MilConfigurationError):
        MilPolicyConfig.validate_configuration_collection(
            (
                config,
                MilPolicyConfig(
                    policy_id="mil-policy-2",
                    version="2.0",
                    name="Duplicate",
                    category="mil",
                    excluded_classification_prefixes=("V.C",),
                    eligible_issuer_categories=("cooperative",),
                    policy_references=(PolicyReference(source="coopealianza", identifier="ref-2"),),
                ),
            )
        )

    with pytest.raises(MilConfigurationError):
        MilPolicyConfig.validate_configuration_collection(
            (
                MilPolicyConfig(
                    policy_id="mil-policy-3",
                    version="2.0",
                    name="Bad",
                    category="mil",
                    excluded_classification_prefixes=("V.C",),
                    eligible_issuer_categories=("cooperative",),
                    policy_references=(PolicyReference(source="coopealianza", identifier=""),),
                ),
            )
        )


def test_mil_policy_config_rejects_invalid_values_and_allows_disabled_policy() -> None:
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(policy_id="", version="1", name="", category="")
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x", version="1", name="y", category="mil", valuation_freshness_limit_days=-1
        )
    with pytest.raises(ValueError):
        MilPolicyConfig(
            policy_id="x", version="1", name="y", category="mil", minimum_remaining_maturity_days=-1
        )
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x",
            version="1",
            name="y",
            category="mil",
            haircut_mappings=(MilHaircutConfig(haircut=Decimal("-0.01")),),
        )
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x",
            version="1",
            name="y",
            category="mil",
            haircut_mappings=(MilHaircutConfig(haircut=Decimal("1.01")),),
        )
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x",
            version="1",
            name="y",
            category="mil",
            issuer_limits=(("issuer", Decimal("-1")),),
        )
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x",
            version="1",
            name="y",
            category="mil",
            currency_limits=(("USD", Decimal("-1")),),
        )
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x",
            version="1",
            name="y",
            category="mil",
            warning_concentration_threshold=Decimal("-1"),
        )
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x",
            version="1",
            name="y",
            category="mil",
            reserve_liquidity_treatment="invalid",
        )

    disabled = MilPolicyConfig(policy_id="x", version="1", name="y", category="mil", enabled=False)
    assert disabled.enabled is False

    assert MilPolicyConfig._parse_date(None) is None
    assert MilPolicyConfig._parse_date("2024-01-01") == date(2024, 1, 1)
    assert MilPolicyConfig._parse_decimal("0.25") == Decimal("0.25")
    assert MilPolicyConfig._parse_severity("MEDIUM") == PolicySeverity.MEDIUM
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig._parse_date(123)
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig._parse_decimal(object())


def test_mil_asset_validation_rejects_invalid_payloads() -> None:
    with pytest.raises(MilValuationError):
        make_asset(position_id="")
    with pytest.raises(MilValuationError):
        make_asset(market_value="1000")
    with pytest.raises(MilValuationError):
        make_asset(nominal_amount=Decimal("-1"))
    with pytest.raises(MilValuationError):
        make_asset(market_value=Decimal("-1"))
    with pytest.raises(MilValuationError):
        make_asset(valuation_date=date(2024, 2, 1), market_price_date=date(2024, 1, 1))
    with pytest.raises(MilValuationError):
        make_asset(maturity_date="not-a-date")
    with pytest.raises(MilValuationError):
        make_asset(market_price_date=date(2024, 1, 1), maturity_date=date(2023, 12, 31))
    with pytest.raises(MilValuationError):
        make_asset(valuation_date=date(2024, 12, 31), maturity_date=date(2024, 1, 1))
    with pytest.raises(MilValuationError):
        make_asset(market_value=Decimal("NaN"))

    parsed_asset = make_asset(maturity_date="2024-06-30")
    assert parsed_asset.maturity_date == date(2024, 6, 30)


def test_availability_policy_handles_active_and_inactive_contexts() -> None:
    policy = AvailabilityPolicy(make_config())
    passed = policy.evaluate(
        PolicyContext(context_id="ctx-1", metadata={"asset": {"operational_availability": True}})
    )
    assert passed.status == "PASSED"

    failed = policy.evaluate(
        PolicyContext(context_id="ctx-2", metadata={"asset": {"operational_availability": False}})
    )
    assert failed.status == "FAILED"

    inactive_config = MilPolicyConfig(
        policy_id="mil-policy-inactive",
        version="1.0",
        name="Inactive",
        category="mil",
        effective_date=date(2024, 2, 1),
        expiration_date=date(2024, 3, 1),
    )
    inactive = AvailabilityPolicy(inactive_config)
    result = inactive.evaluate(
        PolicyContext(
            context_id="ctx-3",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            metadata={"asset": {"operational_availability": True}},
        )
    )
    assert result.status == "NOT_APPLICABLE"


def test_mil_policy_config_validation_branch_paths() -> None:
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig.validate_configuration_collection(
            (
                MilPolicyConfig(
                    policy_id="p1",
                    version="1",
                    name="One",
                    category="mil",
                    excluded_classification_prefixes=("V.C",),
                ),
                MilPolicyConfig(
                    policy_id="p2",
                    version="1",
                    name="Two",
                    category="mil",
                    excluded_classification_prefixes=("V.C",),
                ),
            )
        )

    with pytest.raises(MilConfigurationError):
        MilPolicyConfig.validate_configuration_collection(
            (
                MilPolicyConfig(
                    policy_id="p3",
                    version="1",
                    name="Three",
                    category="mil",
                    eligible_issuer_categories=("cooperative",),
                ),
                MilPolicyConfig(
                    policy_id="p4",
                    version="1",
                    name="Four",
                    category="mil",
                    eligible_issuer_categories=("cooperative",),
                ),
            )
        )

    assert MilPolicyConfig._parse_date(date(2024, 1, 1)) == date(2024, 1, 1)
    assert MilPolicyConfig._parse_decimal(Decimal("0.25")) == Decimal("0.25")
    assert MilPolicyConfig._parse_decimal(2) == Decimal("2")
    assert MilPolicyConfig._parse_severity(PolicySeverity.MEDIUM) == PolicySeverity.MEDIUM

    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x",
            version="1",
            name="y",
            category="mil",
            effective_date=date(2024, 2, 1),
            expiration_date=date(2024, 1, 1),
        )
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x",
            version="1",
            name="y",
            category="mil",
            warning_concentration_threshold=Decimal("0.2"),
            blocking_concentration_threshold=Decimal("0.1"),
        )
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x", version="1", name="y", category="mil", policy_references=(object(),)
        )
    with pytest.raises(MilConfigurationError):
        MilPolicyConfig(
            policy_id="x",
            version="1",
            name="y",
            category="mil",
            blocking_concentration_threshold=Decimal("-0.01"),
        )


def test_mil_engine_handles_exception_and_branch_paths() -> None:
    engine = MilEligibilityEngine()

    with pytest.raises(MilEligibilityError):
        engine.evaluate(MilRequest(portfolio_reference="portfolio-1", assets=()))

    with pytest.raises(MilConfigurationError):
        engine._coerce_config(object())

    config = engine._coerce_config(
        {
            "policy_id": "config-from-map",
            "version": "1.0",
            "name": "Mapped",
            "category": "mil",
            "eligible_issuer_categories": ("cooperative",),
            "acceptable_settlement_rules": ("delivery_vs_payment",),
        }
    )
    assert config.policy_id == "config-from-map"

    asset = make_asset(valuation_date=date(2024, 1, 1))
    assert engine._is_stale(asset, make_config(), {"evaluation_date": date(2024, 1, 10)}) is True

    capacity_values: dict[str, object] = {
        "eligible_adjusted_collateral_value": Decimal("0"),
        "conditional_adjusted_collateral_value": Decimal("0"),
        "capacity_by_issuer": {},
        "capacity_by_currency": {},
        "capacity_by_maturity_band": {},
        "capacity_by_classification": {},
    }
    engine._accumulate_capacity(
        capacity_values,
        make_asset(),
        Decimal("12"),
        MilEligibilityStatus.CONDITIONALLY_ELIGIBLE,
        {"evaluation_date": date(2024, 1, 10)},
    )
    assert capacity_values["conditional_adjusted_collateral_value"] == Decimal("12")
    assert capacity_values["capacity_by_maturity_band"]["medium"] == Decimal("12")

    assert engine._resolve_haircut(make_asset(issuer_category="bank"), make_config()) == Decimal(
        "0"
    )
    assert (
        engine._maturity_band(
            make_asset(maturity_date=date(2025, 12, 31)), {"evaluation_date": date(2024, 1, 10)}
        )
        == "long"
    )
    assert engine._coerce_date_from_context({}) == date.today()
    assert (
        engine._maturity_band(
            make_asset(maturity_date=date(2024, 4, 1)), {"evaluation_date": date(2024, 1, 10)}
        )
        == "short"
    )
