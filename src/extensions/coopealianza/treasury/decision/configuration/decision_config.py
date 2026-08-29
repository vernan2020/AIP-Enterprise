from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from src.extensions.coopealianza.treasury.decision.exceptions import (
    TreasuryDecisionConfigurationError,
)


@dataclass(frozen=True, slots=True)
class DecisionConfig:
    """Immutable configuration for treasury decision generation."""

    policy_id: str
    version: str
    name: str
    category: str = "treasury"
    enabled: bool = True
    effective_date: date | None = None
    expiration_date: date | None = None
    enabled_recommendation_types: tuple[str, ...] = field(default_factory=tuple)
    recommendation_thresholds: dict[str, Decimal] = field(default_factory=dict)
    priority_thresholds: dict[str, Decimal] = field(default_factory=dict)
    factor_weights: dict[str, Decimal] = field(default_factory=dict)
    policy_severity_mappings: dict[str, str] = field(default_factory=dict)
    confidence_bands: dict[str, Decimal] = field(default_factory=dict)
    materiality_thresholds: dict[str, Decimal] = field(default_factory=dict)
    conflicting_signal_resolution: str = "priority"
    duplicate_handling: str = "dedupe"
    partial_input_behavior: str = "review"
    report_ordering: tuple[str, ...] = field(default_factory=tuple)
    policy_references: tuple[str, ...] = field(default_factory=tuple)
    recommended_actions: tuple[str, ...] = field(default_factory=tuple)
    require_policy_references: bool = False

    def __post_init__(self) -> None:
        self._validate()

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "DecisionConfig":
        return cls(
            policy_id=str(mapping.get("policy_id", "")),
            version=str(mapping.get("version", "")),
            name=str(mapping.get("name", "")),
            category=str(mapping.get("category", "treasury")),
            enabled=bool(mapping.get("enabled", True)),
            effective_date=cls._parse_date(mapping.get("effective_date")),
            expiration_date=cls._parse_date(mapping.get("expiration_date")),
            enabled_recommendation_types=tuple(
                str(item) for item in (mapping.get("enabled_recommendation_types") or ())
            ),
            recommendation_thresholds={
                str(key): Decimal(str(value))
                for key, value in (mapping.get("recommendation_thresholds") or {}).items()
            },
            priority_thresholds={
                str(key): Decimal(str(value))
                for key, value in (mapping.get("priority_thresholds") or {}).items()
            },
            factor_weights={
                str(key): Decimal(str(value))
                for key, value in (mapping.get("factor_weights") or {}).items()
            },
            policy_severity_mappings={
                str(key): str(value)
                for key, value in (mapping.get("policy_severity_mappings") or {}).items()
            },
            confidence_bands={
                str(key): Decimal(str(value))
                for key, value in (mapping.get("confidence_bands") or {}).items()
            },
            materiality_thresholds={
                str(key): Decimal(str(value))
                for key, value in (mapping.get("materiality_thresholds") or {}).items()
            },
            conflicting_signal_resolution=str(
                mapping.get("conflicting_signal_resolution", "priority")
            ),
            duplicate_handling=str(mapping.get("duplicate_handling", "dedupe")),
            partial_input_behavior=str(mapping.get("partial_input_behavior", "review")),
            report_ordering=tuple(str(item) for item in (mapping.get("report_ordering") or ())),
            policy_references=tuple(str(item) for item in (mapping.get("policy_references") or ())),
            recommended_actions=tuple(
                str(item) for item in (mapping.get("recommended_actions") or ())
            ),
            require_policy_references=bool(mapping.get("require_policy_references", False)),
        )

    def _validate(self) -> None:
        if not self.policy_id or not self.version or not self.name:
            raise TreasuryDecisionConfigurationError("Policy id, version, and name are required")
        if (
            self.effective_date
            and self.expiration_date
            and self.expiration_date < self.effective_date
        ):
            raise TreasuryDecisionConfigurationError(
                "Expiration date cannot precede effective date"
            )
        if self.effective_date and self.expiration_date and date.today() < self.effective_date:
            raise TreasuryDecisionConfigurationError("Configuration is not yet effective")
        if self.effective_date and self.expiration_date and date.today() > self.expiration_date:
            raise TreasuryDecisionConfigurationError("Configuration has expired")
        for key, value in self.recommendation_thresholds.items():
            if value < 0:
                raise TreasuryDecisionConfigurationError("Threshold values cannot be negative")
        for key, value in self.materiality_thresholds.items():
            if value < 0 or value > Decimal("1"):
                raise TreasuryDecisionConfigurationError(
                    "Materiality thresholds must be between 0 and 100%"
                )
        if (
            self.priority_thresholds.get("warning")
            and self.priority_thresholds.get("blocking")
            and self.priority_thresholds["warning"] > self.priority_thresholds["blocking"]
        ):
            raise TreasuryDecisionConfigurationError(
                "Warning threshold cannot exceed blocking threshold"
            )
        if self.require_policy_references and not self.policy_references:
            raise TreasuryDecisionConfigurationError("Policy references are required")
        if self.conflicting_signal_resolution not in {"priority", "explain"}:
            raise TreasuryDecisionConfigurationError("Conflicting signal resolution is invalid")
        if self.partial_input_behavior not in {"review", "error"}:
            raise TreasuryDecisionConfigurationError("Partial input behavior is invalid")
        if self.duplicate_handling not in {"dedupe", "allow"}:
            raise TreasuryDecisionConfigurationError("Duplicate handling mode is invalid")
        if len(set(self.enabled_recommendation_types)) != len(self.enabled_recommendation_types):
            raise TreasuryDecisionConfigurationError(
                "Duplicate recommendation types are not allowed"
            )

    @classmethod
    def _parse_date(cls, value: Any) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise TreasuryDecisionConfigurationError("Date values must be date or ISO string")
