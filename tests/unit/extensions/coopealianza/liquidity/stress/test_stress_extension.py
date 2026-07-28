from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow
from aip.domain.liquidity.cashflow.models.projection_result import ProjectionResult
from aip.domain.liquidity.gap.models.gap_result import GapResult
from src.extensions.coopealianza.liquidity.stress.analytics.stress_analytics import StressAnalytics
from src.extensions.coopealianza.liquidity.stress.configuration.stress_policy_config import StressPolicyConfig, StressScenarioConfig
from src.extensions.coopealianza.liquidity.stress.engine.stress_engine import StressEngine
from src.extensions.coopealianza.liquidity.stress.exceptions import StressConfigurationError, StressEvaluationError, StressProviderError, StressReportError, StressScenarioError
from src.extensions.coopealianza.liquidity.stress.models.stress_request import StressRequest
from src.extensions.coopealianza.liquidity.stress.providers.scenario_provider import ScenarioProvider, StaticScenarioProvider
from src.extensions.coopealianza.liquidity.stress.reports.stress_report_builder import StressReportBuilder


class FailingScenarioProvider(ScenarioProvider):
    def get_scenarios(self) -> tuple[StressScenarioConfig, ...]:
        raise RuntimeError("provider boom")


class EmptyScenarioProvider(ScenarioProvider):
    def get_scenarios(self) -> tuple[StressScenarioConfig, ...]:
        return ()


def make_config() -> StressPolicyConfig:
    return StressPolicyConfig(
        policy_id="stress-policy",
        version="1.0",
        name="Stress Policy",
        category="stress",
        effective_date=date(2024, 1, 1),
        expiration_date=date(2030, 1, 1),
        scenarios=(
            StressScenarioConfig(
                scenario_id="s1",
                name="parallel_shift",
                scenario_type="parallel_shift",
                severity=Decimal("0.10"),
                rate_shift=Decimal("0.01"),
                liquidity_factor=Decimal("0.05"),
                concentration_factor=Decimal("0.02"),
                runoff_rate=Decimal("0.05"),
                withdrawal_rate=Decimal("0.03"),
                collateral_multiplier=Decimal("0.90"),
                market_value_multiplier=Decimal("0.10"),
                policy_references=("REF-1",),
                affected_assets=("asset-1",),
                affected_buckets=("O/N",),
                assumptions=("assume stable market",),
                warnings=("watch liquidity",),
            ),
        ),
    )


def make_gap_result() -> GapResult:
    return GapResult(
        valuation_date=date(2024, 1, 10),
        gap_type="daily",
        net_gap=Decimal("1000"),
        gross_inflow=Decimal("4000"),
        gross_outflow=Decimal("5000"),
        incremental_gap=Decimal("100"),
        cumulative_gap=Decimal("1000"),
        summary_value=Decimal("1000"),
    )


def make_projection_result() -> ProjectionResult:
    return ProjectionResult(
        projection_type="contractual",
        projected_cashflows=(
            ProjectedCashFlow(payment_date=date(2024, 1, 15), amount=Decimal("-500"), currency="USD", cash_flow_type="outflow"),
            ProjectedCashFlow(payment_date=date(2024, 1, 16), amount=Decimal("300"), currency="USD", cash_flow_type="inflow"),
        ),
    )


def test_stress_configuration_is_valid_and_immutable() -> None:
    config = make_config()
    assert config.scenarios[0].scenario_type == "parallel_shift"
    assert config.effective_date == date(2024, 1, 1)
    with pytest.raises(AttributeError):
        config.scenarios += (StressScenarioConfig(scenario_id="s2", name="x", scenario_type="twist", severity=Decimal("0.01"), policy_references=("REF-2",)),)


def test_stress_configuration_rejects_invalid_dates_and_values() -> None:
    with pytest.raises(StressConfigurationError):
        StressPolicyConfig(policy_id="x", version="1", name="y", category="stress", effective_date=date(2024, 2, 1), expiration_date=date(2024, 1, 1))
    with pytest.raises(StressConfigurationError):
        StressScenarioConfig(scenario_id="bad", name="bad", scenario_type="parallel_shift", severity=Decimal("-0.01"), policy_references=("REF-1",))
    with pytest.raises(StressConfigurationError):
        StressScenarioConfig(scenario_id="bad2", name="bad2", scenario_type="parallel_shift", severity=Decimal("1.01"), policy_references=("REF-1",))
    with pytest.raises(StressConfigurationError):
        StressPolicyConfig(policy_id="x", version="1", name="y", category="stress", scenarios=(StressScenarioConfig(scenario_id="a", name="a", scenario_type="parallel_shift", severity=Decimal("0.1"), policy_references=("REF-1",)), StressScenarioConfig(scenario_id="a", name="b", scenario_type="twist", severity=Decimal("0.1"), policy_references=("REF-2",))))
    with pytest.raises(StressConfigurationError):
        StressScenarioConfig(scenario_id="bad3", name="bad3", scenario_type="combined", policy_references=(), combined_scenario_ids=("s1",))


def test_stress_configuration_from_mapping_supports_expired_and_disabled_states() -> None:
    mapping = {
        "policy_id": "p2",
        "version": "2.0",
        "name": "Mapped",
        "category": "stress",
        "enabled": True,
        "effective_date": "2024-01-01",
        "expiration_date": "2024-03-01",
        "scenarios": [{"scenario_id": "s2", "name": "deposit_runoff", "scenario_type": "deposit_runoff", "severity": "0.05", "runoff_rate": "0.20", "policy_references": ["REF-2"], "affected_assets": ["asset-2"], "affected_buckets": ["1D"], "assumptions": ["runoff"], "warnings": ["warn"]}],
    }
    config = StressPolicyConfig.from_mapping(mapping)
    assert config.scenarios[0].runoff_rate == Decimal("0.20")
    assert config.scenarios[0].policy_references == ("REF-2",)


def test_stress_policy_validation_covers_unsupported_and_empty_inputs() -> None:
    with pytest.raises(StressConfigurationError):
        StressScenarioConfig(scenario_id="bad", name="bad", scenario_type="unsupported", policy_references=("REF",))
    with pytest.raises(StressConfigurationError):
        StressScenarioConfig(scenario_id="combined", name="combined", scenario_type="combined", policy_references=("REF",), combined_scenario_ids=())
    with pytest.raises(StressConfigurationError):
        StressPolicyConfig(policy_id="", version="1", name="n", category="stress")
    with pytest.raises(StressConfigurationError):
        StressScenarioConfig(scenario_id="bad", name="bad", scenario_type="parallel_shift", severity=Decimal("0.20"), collateral_multiplier=Decimal("1.01"), policy_references=("REF",))
    assert StressPolicyConfig._parse_date(date(2024, 1, 2)) == date(2024, 1, 2)
    assert StressPolicyConfig._parse_date("2024-01-03") == date(2024, 1, 3)
    with pytest.raises(StressConfigurationError):
        StressPolicyConfig._parse_date(object())


def test_stress_engine_evaluates_scenarios_using_existing_liquidity_outputs() -> None:
    engine = StressEngine()
    request = StressRequest(
        portfolio_reference="portfolio-1",
        gap_result=make_gap_result(),
        projection_result=make_projection_result(),
        configuration=make_config(),
        scenario_provider=StaticScenarioProvider(make_config().scenarios),
    )

    result = engine.evaluate(request)

    assert result.total_scenarios == 1
    assert result.scenario_results[0].scenario_name == "parallel_shift"
    assert result.scenario_results[0].stressed_gap == Decimal("1170")
    assert result.scenario_results[0].stressed_outflow == Decimal("5250")
    assert result.summary["max_stressed_gap"] == Decimal("1170")
    assert result.explanation is not None


def test_deposit_runoff_scenarios_cover_zero_partial_and_full_runoff() -> None:
    config = StressPolicyConfig(policy_id="p", version="1", name="n", category="stress", scenarios=(StressScenarioConfig(scenario_id="r0", name="zero", scenario_type="deposit_runoff", runoff_rate=Decimal("0"), policy_references=("REF",)), StressScenarioConfig(scenario_id="r1", name="partial", scenario_type="deposit_runoff", runoff_rate=Decimal("0.25"), policy_references=("REF",)), StressScenarioConfig(scenario_id="r2", name="full", scenario_type="deposit_runoff", runoff_rate=Decimal("1"), policy_references=("REF",))))
    engine = StressEngine()
    result = engine.evaluate(StressRequest(portfolio_reference="portfolio", gap_result=make_gap_result(), projection_result=make_projection_result(), configuration=config))
    assert result.scenario_results[0].stressed_gap == Decimal("1000")
    assert result.scenario_results[1].stressed_gap == Decimal("1250")
    assert result.scenario_results[2].stressed_gap == Decimal("2000")
    assert result.scenario_results[1].stressed_inflow == Decimal("3000")
    assert result.summary["max_stressed_gap"] == Decimal("2000")


def test_wholesale_funding_shock_scenarios_cover_withdrawal_and_maturity_buckets() -> None:
    config = StressPolicyConfig(policy_id="p", version="1", name="n", category="stress", scenarios=(StressScenarioConfig(scenario_id="w0", name="zero", scenario_type="wholesale_funding_shock", withdrawal_rate=Decimal("0"), policy_references=("REF",), affected_buckets=("O/N", "1W")), StressScenarioConfig(scenario_id="w1", name="partial", scenario_type="wholesale_funding_shock", withdrawal_rate=Decimal("0.50"), policy_references=("REF",), affected_buckets=("O/N",)), StressScenarioConfig(scenario_id="w2", name="full", scenario_type="wholesale_funding_shock", withdrawal_rate=Decimal("1"), policy_references=("REF",), affected_buckets=("1M",))))
    engine = StressEngine()
    result = engine.evaluate(StressRequest(portfolio_reference="portfolio", gap_result=make_gap_result(), projection_result=make_projection_result(), configuration=config))
    assert result.scenario_results[0].stressed_outflow == Decimal("5000")
    assert result.scenario_results[1].stressed_outflow == Decimal("7500")
    assert result.scenario_results[2].stressed_outflow == Decimal("10000")
    assert result.scenario_results[2].affected_buckets == ("1M",)


def test_collateral_haircut_and_market_liquidity_deterioration_scenarios() -> None:
    config = StressPolicyConfig(policy_id="p", version="1", name="n", category="stress", scenarios=(StressScenarioConfig(scenario_id="c1", name="haircut", scenario_type="collateral_haircut", severity=Decimal("0.20"), collateral_multiplier=Decimal("0.50"), policy_references=("REF",), affected_assets=("asset-1",)), StressScenarioConfig(scenario_id="m1", name="market", scenario_type="market_liquidity_deterioration", severity=Decimal("0.10"), market_value_multiplier=Decimal("0.20"), policy_references=("REF",), affected_assets=("asset-2",))))
    engine = StressEngine()
    result = engine.evaluate(StressRequest(portfolio_reference="portfolio", gap_result=make_gap_result(), projection_result=make_projection_result(), configuration=config))
    assert result.scenario_results[0].stressed_gap == Decimal("1500")
    assert result.scenario_results[1].stressed_gap == Decimal("1200")
    assert result.scenario_results[0].stressed_outflow == Decimal("6000")
    assert result.scenario_results[1].affected_assets == ("asset-2",)


def test_combined_scenarios_are_isolated_and_deterministic() -> None:
    config = StressPolicyConfig(policy_id="p", version="1", name="n", category="stress", scenarios=(StressScenarioConfig(scenario_id="c1", name="alpha", scenario_type="parallel_shift", severity=Decimal("0.10"), policy_references=("REF",)), StressScenarioConfig(scenario_id="c2", name="beta", scenario_type="parallel_shift", severity=Decimal("0.20"), policy_references=("REF",)), StressScenarioConfig(scenario_id="combined", name="combined", scenario_type="combined", severity=Decimal("0.10"), policy_references=("REF",), combined_scenario_ids=("c1", "c2"), affected_assets=("asset-3",))))
    engine = StressEngine()
    result = engine.evaluate(StressRequest(portfolio_reference="portfolio", gap_result=make_gap_result(), projection_result=make_projection_result(), configuration=config))
    assert result.scenario_results[-1].stressed_gap == Decimal("2300")
    assert result.scenario_results[-1].affected_assets == ("asset-3",)
    assert [item.scenario_name for item in result.scenario_results] == ["alpha", "beta", "combined"]


def test_stress_engine_handles_successful_and_failed_requests() -> None:
    engine = StressEngine()
    with pytest.raises(StressEvaluationError):
        engine.evaluate(StressRequest(portfolio_reference="", gap_result=make_gap_result(), projection_result=make_projection_result(), configuration=make_config()))
    with pytest.raises(StressEvaluationError):
        engine.evaluate(StressRequest(portfolio_reference="portfolio", configuration=make_config()))
    with pytest.raises(StressProviderError):
        engine.evaluate(StressRequest(portfolio_reference="portfolio", gap_result=make_gap_result(), projection_result=make_projection_result(), configuration=make_config(), scenario_provider=FailingScenarioProvider()))
    empty_config = StressPolicyConfig(policy_id="empty", version="1", name="empty", category="stress", scenarios=())
    with pytest.raises(StressEvaluationError):
        engine.evaluate(StressRequest(portfolio_reference="portfolio", gap_result=make_gap_result(), projection_result=make_projection_result(), configuration=empty_config))

    combined_scenario = object.__new__(StressScenarioConfig)
    object.__setattr__(combined_scenario, "scenario_id", "combined")
    object.__setattr__(combined_scenario, "name", "combined")
    object.__setattr__(combined_scenario, "scenario_type", "combined")
    object.__setattr__(combined_scenario, "severity", Decimal("0"))
    object.__setattr__(combined_scenario, "rate_shift", Decimal("0"))
    object.__setattr__(combined_scenario, "liquidity_factor", Decimal("0"))
    object.__setattr__(combined_scenario, "concentration_factor", Decimal("0"))
    object.__setattr__(combined_scenario, "runoff_rate", Decimal("0"))
    object.__setattr__(combined_scenario, "withdrawal_rate", Decimal("0"))
    object.__setattr__(combined_scenario, "collateral_multiplier", Decimal("1"))
    object.__setattr__(combined_scenario, "market_value_multiplier", Decimal("1"))
    object.__setattr__(combined_scenario, "policy_references", ("REF",))
    object.__setattr__(combined_scenario, "affected_assets", ())
    object.__setattr__(combined_scenario, "affected_buckets", ())
    object.__setattr__(combined_scenario, "assumptions", ())
    object.__setattr__(combined_scenario, "warnings", ())
    object.__setattr__(combined_scenario, "combined_scenario_ids", ())
    object.__setattr__(combined_scenario, "effective_date", None)
    object.__setattr__(combined_scenario, "expiration_date", None)

    with pytest.raises(StressEvaluationError):
        engine._evaluate_combined_scenario(combined_scenario, make_gap_result(), make_projection_result(), {})

    missing_scenario = StressScenarioConfig(scenario_id="missing", name="missing", scenario_type="combined", policy_references=("REF",), combined_scenario_ids=("not-there",))
    with pytest.raises(StressEvaluationError):
        engine._evaluate_combined_scenario(missing_scenario, make_gap_result(), make_projection_result(), {})

    with pytest.raises(StressConfigurationError):
        engine._coerce_config(object())
    assert engine._coerce_config({"policy_id": "p", "version": "1", "name": "n", "category": "stress", "scenarios": []}).policy_id == "p"


def test_analytics_builds_expected_explanations_and_decimal_precision() -> None:
    analytics = StressAnalytics()
    explanation = analytics.build_gap_deterioration(baseline_gap=Decimal("1000"), stressed_gap=Decimal("1250"))
    assert explanation.concise_conclusion == "Gap deterioration"
    assert explanation.supporting_factors[0].value == Decimal("250")
    explanation = analytics.build_resilience_ratio(baseline_gap=Decimal("1000"), stressed_gap=Decimal("1250"))
    assert explanation.supporting_factors[0].value == Decimal("1.25")
    explanation = analytics.build_comparison(baseline_gap=Decimal("1000"), stressed_gap=Decimal("1250"), baseline_outflow=Decimal("5000"), stressed_outflow=Decimal("6000"))
    assert explanation.supporting_factors[1].value == Decimal("1000")
    explanation = analytics.build_liquidity_coverage_variation(baseline_outflow=Decimal("5000"), stressed_outflow=Decimal("6000"))
    assert explanation.supporting_factors[0].value == Decimal("1000")
    explanation = analytics.build_collateral_capacity_variation(baseline_capacity=Decimal("100"), stressed_capacity=Decimal("80"))
    assert explanation.supporting_factors[0].value == Decimal("20")
    explanation = analytics.build_hqla_variation(baseline_capacity=Decimal("100"), stressed_capacity=Decimal("80"))
    assert explanation.supporting_factors[0].value == Decimal("20")
    explanation = analytics.build_issuer_concentration_change(baseline=Decimal("100"), stressed=Decimal("120"))
    assert explanation.supporting_factors[0].value == Decimal("20")
    explanation = analytics.build_currency_concentration_change(baseline=Decimal("100"), stressed=Decimal("90"))
    assert explanation.supporting_factors[0].value == Decimal("-10")
    with pytest.raises(Exception):
        analytics.build_explanation(conclusion="Empty", factors=[])


def test_report_builder_includes_metadata_and_orders_results() -> None:
    result = StressEngine().evaluate(StressRequest(portfolio_reference="portfolio", gap_result=make_gap_result(), projection_result=make_projection_result(), configuration=make_config()))
    report = StressReportBuilder().build(result)
    assert report["scenario_results"][0]["scenario_name"] == "parallel_shift"
    assert report["warnings"] == ["watch liquidity"]
    assert report["policy_references"] == ["REF-1"]
    assert report["calculation_id"] == "stress-portfolio"


def test_report_builder_raises_for_missing_result() -> None:
    with pytest.raises(StressReportError):
        StressReportBuilder().build(None)  # type: ignore[arg-type]


def test_report_builder_handles_warnings_and_empty_assets() -> None:
    result = StressEngine().evaluate(StressRequest(portfolio_reference="portfolio", gap_result=make_gap_result(), projection_result=make_projection_result(), configuration=StressPolicyConfig(policy_id="p", version="1", name="n", category="stress", scenarios=(StressScenarioConfig(scenario_id="s1", name="beta", scenario_type="parallel_shift", severity=Decimal("0.10"), policy_references=("REF",), warnings=("warn",)), StressScenarioConfig(scenario_id="s2", name="alpha", scenario_type="parallel_shift", severity=Decimal("0.05"), policy_references=("REF",))))))
    report = StressReportBuilder().build(result)
    assert report["warnings"] == ["warn"]
    assert report["affected_assets"] == []
    assert report["scenario_results"][0]["scenario_name"] == "alpha"
    assert report["scenario_results"][1]["scenario_name"] == "beta"


def test_provider_error_translation_and_exception_paths() -> None:
    with pytest.raises(StressConfigurationError):
        StressScenarioConfig(scenario_id="bad", name="", scenario_type="", policy_references=("REF",))
    with pytest.raises(StressScenarioError):
        raise StressScenarioError("scenario issue")

