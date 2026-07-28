from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from src.extensions.coopealianza.liquidity.mil.analytics.mil_analytics import MilAnalytics
from src.extensions.coopealianza.liquidity.mil.configuration.mil_policy_config import MilPolicyConfig
from src.extensions.coopealianza.liquidity.mil.enums.mil_eligibility_status import MilEligibilityStatus
from src.extensions.coopealianza.liquidity.mil.exceptions import MilCapacityError, MilConfigurationError, MilEligibilityError, MilProviderError
from src.extensions.coopealianza.liquidity.mil.models.mil_capacity_result import MilCapacityResult
from src.extensions.coopealianza.liquidity.mil.models.mil_position_result import MilPositionResult
from src.extensions.coopealianza.liquidity.mil.models.mil_request import MilRequest
from src.extensions.coopealianza.liquidity.mil.models.mil_result import MilResult
from src.extensions.coopealianza.liquidity.mil.policies.availability_policy import AvailabilityPolicy


class MilEligibilityEngine:
    """Evaluate MIL eligibility and collateral capacity for a portfolio of assets."""

    def __init__(self) -> None:
        self._analytics = MilAnalytics()

    def evaluate(self, request: MilRequest) -> MilResult:
        assets = tuple(request.assets)
        if not assets:
            raise MilEligibilityError("At least one asset is required")

        config = self._coerce_config(request.configuration)
        policy_context = dict(request.policy_context or {})
        positions: list[MilPositionResult] = []
        status_counts: Counter[str] = Counter()
        capacity_values: dict[str, Any] = {
            "total_market_value_evaluated": Decimal("0"),
            "eligible_market_value": Decimal("0"),
            "conditionally_eligible_market_value": Decimal("0"),
            "ineligible_market_value": Decimal("0"),
            "unknown_market_value": Decimal("0"),
            "eligible_adjusted_collateral_value": Decimal("0"),
            "conditional_adjusted_collateral_value": Decimal("0"),
            "total_potential_collateral_capacity": Decimal("0"),
            "capacity_by_issuer": {},
            "capacity_by_currency": {},
            "capacity_by_maturity_band": {},
            "capacity_by_classification": {},
            "encumbered_value": Decimal("0"),
            "unavailable_value": Decimal("0"),
            "excluded_classification_value": Decimal("0"),
        }
        eligible_capacity = Decimal("0")
        conditional_capacity = Decimal("0")
        total_market_value = Decimal("0")

        for asset in assets:
            status, blocking_factors, warning_factors, haircut, adjusted_value, reasoning = self._evaluate_asset(asset, config, policy_context)
            status_counts[status.value] += 1
            total_market_value += asset.market_value
            if status == MilEligibilityStatus.ELIGIBLE:
                eligible_capacity += adjusted_value
            elif status == MilEligibilityStatus.CONDITIONALLY_ELIGIBLE:
                conditional_capacity += adjusted_value
            position = MilPositionResult(
                position_id=asset.position_id,
                instrument_id=asset.instrument_id,
                issuer=asset.issuer,
                issuer_category=asset.issuer_category,
                classification=asset.classification,
                eligibility_status=status,
                blocking_factors=blocking_factors,
                warning_factors=warning_factors,
                haircut=haircut,
                adjusted_value=adjusted_value,
                market_value=asset.market_value,
                configuration_version=config.version,
                policy_references=tuple(ref.identifier for ref in config.policy_references),
                assumptions=("No FX conversion applied",),
                warnings=(),
                recommended_action=None,
                evidence=(
                    {"position_id": asset.position_id, "reason": reasoning},
                ),
            )
            positions.append(position)

            self._accumulate_capacity(capacity_values, asset, adjusted_value, status, policy_context)

        capacity_values["total_market_value_evaluated"] = total_market_value
        capacity_values["eligible_market_value"] = sum((p.market_value for p in positions if p.eligibility_status == MilEligibilityStatus.ELIGIBLE), Decimal("0"))
        capacity_values["conditionally_eligible_market_value"] = sum((p.market_value for p in positions if p.eligibility_status == MilEligibilityStatus.CONDITIONALLY_ELIGIBLE), Decimal("0"))
        capacity_values["ineligible_market_value"] = sum((p.market_value for p in positions if p.eligibility_status == MilEligibilityStatus.NOT_ELIGIBLE), Decimal("0"))
        capacity_values["unknown_market_value"] = sum((p.market_value for p in positions if p.eligibility_status == MilEligibilityStatus.UNKNOWN), Decimal("0"))
        capacity_values["eligible_adjusted_collateral_value"] = eligible_capacity
        capacity_values["conditional_adjusted_collateral_value"] = conditional_capacity
        capacity_values["total_potential_collateral_capacity"] = eligible_capacity + conditional_capacity

        capacity = MilCapacityResult(**capacity_values)

        status_mapping = {status: count for status, count in status_counts.items()}
        explanation = self._analytics.build_explanation(
            conclusion="MIL eligibility evaluation completed",
            factors=[
                ("eligible_capacity", eligible_capacity),
                ("conditional_capacity", conditional_capacity),
            ],
            source_references=[ref.identifier for ref in config.policy_references],
        )
        return MilResult(
            portfolio_reference=request.portfolio_reference,
            configuration_version=config.version,
            calculation_date=request.policy_context.get("evaluation_date", date.today()),
            total_assets_evaluated=len(assets),
            positions=tuple(positions),
            capacity=capacity,
            status_counts=status_mapping,
            policy_references=tuple(ref.identifier for ref in config.policy_references),
            warnings=(),
            recommended_actions=(),
            explanation=explanation,
            calculation_identifier=f"mil-{request.portfolio_reference}",
        )

    def _evaluate_asset(self, asset: Any, config: MilPolicyConfig, policy_context: dict[str, Any]) -> tuple[MilEligibilityStatus, tuple[str, ...], tuple[str, ...], Decimal, Decimal, str]:
        blocking_factors: list[str] = []
        warning_factors: list[str] = []
        adjusted_value = Decimal("0")
        haircut = Decimal("0")
        if asset.classification.startswith(tuple(config.excluded_classification_prefixes)):
            blocking_factors.append("excluded_classification")
        if asset.issuer_category not in config.eligible_issuer_categories:
            blocking_factors.append("ineligible_issuer")
        if asset.encumbrance_status.lower() != "unencumbered":
            blocking_factors.append("encumbrance")
        if not asset.operational_availability:
            blocking_factors.append("operational_unavailable")
        if asset.settlement_capability not in config.acceptable_settlement_rules:
            blocking_factors.append("settlement")
        if self._is_stale(asset, config, policy_context):
            warning_factors.append("stale_valuation")
        if self._is_below_maturity(asset, config, policy_context):
            blocking_factors.append("maturity")
        if config.reserve_liquidity_treatment == "conditional" and asset.reserve_liquidity_status.lower() == "reserve":
            warning_factors.append("reserve_liquidity")

        haircut = self._resolve_haircut(asset, config)
        adjusted_value = asset.market_value * (Decimal("1") - haircut)

        if blocking_factors:
            return MilEligibilityStatus.NOT_ELIGIBLE, tuple(blocking_factors), tuple(warning_factors), haircut, adjusted_value, "; ".join(blocking_factors)

        if warning_factors:
            return MilEligibilityStatus.CONDITIONALLY_ELIGIBLE, tuple(blocking_factors), tuple(warning_factors), haircut, adjusted_value, "; ".join(warning_factors)

        return MilEligibilityStatus.ELIGIBLE, tuple(blocking_factors), tuple(warning_factors), haircut, adjusted_value, "eligible"

    def _is_stale(self, asset: Any, config: MilPolicyConfig, policy_context: dict[str, Any]) -> bool:
        evaluation_date = self._coerce_date_from_context(policy_context)
        try:
            age = (evaluation_date - asset.valuation_date).days
        except TypeError:
            return True
        return age > config.valuation_freshness_limit_days

    def _is_below_maturity(self, asset: Any, config: MilPolicyConfig, policy_context: dict[str, Any]) -> bool:
        evaluation_date = self._coerce_date_from_context(policy_context)
        remaining_days = (asset.maturity_date - evaluation_date).days
        return remaining_days < config.minimum_remaining_maturity_days

    def _resolve_haircut(self, asset: Any, config: MilPolicyConfig) -> Decimal:
        for mapping in config.haircut_mappings:
            if mapping.issuer_category and mapping.issuer_category != asset.issuer_category:
                continue
            if mapping.instrument_category and mapping.instrument_category != asset.classification:
                continue
            if mapping.currency and mapping.currency != asset.currency:
                continue
            if mapping.classification and mapping.classification != asset.classification:
                continue
            if mapping.haircut is None:
                continue
            return mapping.haircut
        return Decimal("0")

    def _accumulate_capacity(self, capacity_values: dict[str, Any], asset: Any, adjusted_value: Decimal, status: MilEligibilityStatus, policy_context: dict[str, Any]) -> None:
        if status == MilEligibilityStatus.ELIGIBLE:
            capacity_values["eligible_adjusted_collateral_value"] = capacity_values["eligible_adjusted_collateral_value"] + adjusted_value
        elif status == MilEligibilityStatus.CONDITIONALLY_ELIGIBLE:
            capacity_values["conditional_adjusted_collateral_value"] = capacity_values["conditional_adjusted_collateral_value"] + adjusted_value

        if status not in {MilEligibilityStatus.ELIGIBLE, MilEligibilityStatus.CONDITIONALLY_ELIGIBLE}:
            return

        maturity_band = self._maturity_band(asset, policy_context)
        capacity_values["capacity_by_issuer"][asset.issuer] = capacity_values["capacity_by_issuer"].get(asset.issuer, Decimal("0")) + adjusted_value
        capacity_values["capacity_by_currency"][asset.currency] = capacity_values["capacity_by_currency"].get(asset.currency, Decimal("0")) + adjusted_value
        capacity_values["capacity_by_maturity_band"][maturity_band] = capacity_values["capacity_by_maturity_band"].get(maturity_band, Decimal("0")) + adjusted_value
        if status == MilEligibilityStatus.ELIGIBLE:
            capacity_values["capacity_by_classification"][asset.classification] = capacity_values["capacity_by_classification"].get(asset.classification, Decimal("0")) + adjusted_value

    def _maturity_band(self, asset: Any, policy_context: dict[str, Any]) -> str:
        remaining = (asset.maturity_date - self._coerce_date_from_context(policy_context)).days
        if remaining < 90:
            return "short"
        if remaining < 365:
            return "medium"
        return "long"

    def _coerce_date_from_context(self, policy_context: dict[str, Any]) -> date:
        evaluation_date = policy_context.get("evaluation_date")
        if isinstance(evaluation_date, date):
            return evaluation_date
        return date.today()

    def _coerce_config(self, config: Any) -> MilPolicyConfig:
        if isinstance(config, MilPolicyConfig):
            return config
        if isinstance(config, dict):
            return MilPolicyConfig.from_mapping(config)
        raise MilConfigurationError("MIL configuration must be a MilPolicyConfig or mapping")
