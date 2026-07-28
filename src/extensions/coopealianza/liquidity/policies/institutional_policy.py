from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import LiquidityPolicyConfig
from src.extensions.coopealianza.liquidity.exceptions import InstitutionalPolicyError


class InstitutionalPolicy(Policy):
    """Extension policy base class that respects effective and expiration dates."""

    def __init__(self, config: LiquidityPolicyConfig, *, description: str) -> None:
        super().__init__(
            policy_id=config.policy_id,
            name=config.name,
            description=description,
            version=config.version,
            enabled=config.enabled,
            severity=config.severity,
            category=config.category,
            reference=PolicyReference(source="coopealianza", identifier=config.policy_id),
            priority=config.priority,
        )
        self._config = config

    def evaluate(self, context: PolicyContext) -> EvaluationResult:
        if not self._is_active(context):
            return EvaluationResult(
                policy_id=self.policy_id,
                status="NOT_APPLICABLE",
                message="Policy is outside its effective period",
                severity=self.severity,
                references=self._config.to_policy_reference(),
                timestamp=context.timestamp or self._timestamp(),
                evaluation_duration=None,
                context_id=context.context_id,
            )
        return super().evaluate(context)

    def _is_active(self, context: PolicyContext) -> bool:
        effective = self._config.effective_date
        expiration = self._config.expiration_date
        now = context.timestamp or self._timestamp()
        if effective is not None and now.date() < effective:
            return False
        if expiration is not None and now.date() > expiration:
            return False
        return True

    def _coerce_asset(self, context: PolicyContext) -> dict[str, Any]:
        asset = context.metadata.get("asset") if context.metadata else None
        if isinstance(asset, dict):
            return asset
        raise InstitutionalPolicyError("Asset context must be a dictionary")

    def _result(self, context: PolicyContext, status: str, message: str, *, severity: PolicySeverity | None = None) -> EvaluationResult:
        return EvaluationResult(
            policy_id=self.policy_id,
            status=status,
            message=message,
            severity=severity or self.severity,
            references=self._config.to_policy_reference(),
            timestamp=context.timestamp or self._timestamp(),
            evaluation_duration=None,
            context_id=context.context_id,
        )

    def _timestamp(self) -> datetime:
        return datetime.now(timezone.utc)
