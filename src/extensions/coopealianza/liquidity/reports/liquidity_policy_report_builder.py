from __future__ import annotations

from datetime import datetime
from typing import Any

from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.base.policy_result import PolicyResult
from src.extensions.coopealianza.liquidity.exceptions import (
    InstitutionalProviderError,
    PolicyReportError,
)
from src.extensions.coopealianza.liquidity.providers.institutional_policy_provider import (
    InstitutionalPolicyProvider,
)
from src.extensions.coopealianza.liquidity.providers.portfolio_asset_provider import (
    PortfolioAssetProvider,
)
from src.extensions.coopealianza.liquidity.reports.liquidity_policy_report import (
    LiquidityPolicyReport,
)


class LiquidityPolicyReportBuilder:
    """Build deterministic liquidity policy reports from evaluation results."""

    def build(
        self,
        evaluations: tuple[PolicyResult, ...],
        *,
        portfolio_reference: str,
        policy_configuration_version: str,
        evaluation_date: datetime,
        asset_id: str | None = None,
        policy_context: PolicyContext | None = None,
    ) -> LiquidityPolicyReport:
        if not evaluations:
            raise PolicyReportError("At least one policy evaluation is required")

        ordered = sorted(
            evaluations,
            key=lambda item: (
                item.policy_id,
                item.context_id,
                getattr(item, "message", ""),
            ),
        )
        blocking_failures = tuple(
            result.policy_id for result in ordered if result.status == "FAILED"
        )
        evidence = tuple(
            {"policy_id": result.policy_id, "status": result.status} for result in ordered
        )
        explanation = ExplanationBuilder().build(
            concise_conclusion="Institutional liquidity policy evaluation completed",
            factors=[
                ExplanationFactor(
                    name="evaluations", value=0, direction="higher_is_better", contribution=0
                )
            ],
            assumptions=(),
            warnings=(),
            source_references=(),
        )
        return LiquidityPolicyReport(
            evaluation_date=evaluation_date,
            portfolio_reference=portfolio_reference,
            policy_configuration_version=policy_configuration_version,
            total_policies_evaluated=len(ordered),
            passed_count=sum(1 for result in ordered if result.status == "PASSED"),
            failed_count=sum(1 for result in ordered if result.status == "FAILED"),
            warning_count=sum(1 for result in ordered if result.status == "WARNING"),
            not_applicable_count=sum(1 for result in ordered if result.status == "NOT_APPLICABLE"),
            blocking_failures=blocking_failures,
            affected_assets=tuple(filter(None, [asset_id])),
            affected_issuers=(),
            policy_references=tuple(
                (reference.source, reference.identifier)
                for result in ordered
                for reference in result.references
            ),
            evidence=evidence,
            recommended_actions=(),
            assumptions=(),
            warnings=(),
            calculation_identifier=f"liquidity-report-{len(ordered)}",
            evaluations=ordered,
            explanation=explanation,
        )

    def build_provider_assets(
        self, provider: PortfolioAssetProvider, portfolio_reference: str
    ) -> tuple[dict[str, Any], ...]:
        try:
            assets = provider.get_assets(portfolio_reference)
        except Exception as exc:
            raise InstitutionalProviderError("Portfolio asset provider failed") from exc
        if not isinstance(assets, tuple):
            raise InstitutionalProviderError("Portfolio asset provider returned malformed data")
        if any(not isinstance(asset, dict) for asset in assets):
            raise InstitutionalProviderError("Portfolio asset provider returned malformed data")
        if any(not asset.get("asset_id") or not asset.get("classification") for asset in assets):
            raise InstitutionalProviderError("Portfolio asset provider returned malformed data")
        return assets

    def build_provider_policy_data(
        self, provider: InstitutionalPolicyProvider, portfolio_reference: str
    ) -> dict[str, Any]:
        try:
            data = provider.get_policy_data(portfolio_reference)
        except Exception as exc:
            raise InstitutionalProviderError("Institutional policy provider failed") from exc
        if not isinstance(data, dict):
            raise InstitutionalProviderError(
                "Institutional policy provider returned malformed data"
            )
        return data
