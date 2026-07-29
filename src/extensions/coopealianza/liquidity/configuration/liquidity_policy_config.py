from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity
from src.extensions.coopealianza.liquidity.configuration.policy_reference_config import (
    PolicyReferenceConfig,
)
from src.extensions.coopealianza.liquidity.exceptions import InstitutionalConfigurationError


@dataclass(frozen=True, slots=True)
class LiquidityPolicyConfig:
    """Immutable typed configuration for Coopealianza liquidity policies."""

    policy_id: str
    version: str
    name: str
    category: str
    enabled: bool = True
    effective_date: date | None = None
    expiration_date: date | None = None
    severity: PolicySeverity = PolicySeverity.MEDIUM
    issuer_categories: tuple[str, ...] = field(default_factory=tuple)
    instrument_classifications: tuple[str, ...] = field(default_factory=tuple)
    excluded_classification_prefixes: tuple[str, ...] = field(default_factory=tuple)
    issuer_limit: Decimal | None = None
    concentration_warning_limit: Decimal | None = None
    concentration_blocking_limit: Decimal | None = None
    minimum_liquidity_warning: Decimal | None = None
    minimum_liquidity_blocking: Decimal | None = None
    minimum_marketability_score: Decimal | None = None
    minimum_price_availability_score: Decimal | None = None
    required_marketability_attributes: tuple[str, ...] = field(default_factory=tuple)
    required_encumbrance_status: tuple[str, ...] = field(default_factory=tuple)
    policy_references: tuple[PolicyReferenceConfig, ...] = field(default_factory=tuple)
    recommended_action: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        self._validate()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "LiquidityPolicyConfig":
        severity = mapping.get("severity")
        if isinstance(severity, str):
            severity = PolicySeverity[severity]
        references = tuple(
            PolicyReferenceConfig(**reference) if isinstance(reference, dict) else reference
            for reference in mapping.get("policy_references", ())
        )
        return cls(
            policy_id=str(mapping["policy_id"]),
            version=str(mapping["version"]),
            name=str(mapping["name"]),
            category=str(mapping["category"]),
            enabled=bool(mapping.get("enabled", True)),
            effective_date=cls._parse_date(mapping.get("effective_date")),
            expiration_date=cls._parse_date(mapping.get("expiration_date")),
            severity=severity or PolicySeverity.MEDIUM,
            issuer_categories=tuple(str(item) for item in mapping.get("issuer_categories", ()) or ()),
            instrument_classifications=tuple(str(item) for item in mapping.get("instrument_classifications", ()) or ()),
            excluded_classification_prefixes=tuple(str(item) for item in mapping.get("excluded_classification_prefixes", ()) or ()),
            issuer_limit=cls._parse_decimal(mapping.get("issuer_limit")),
            concentration_warning_limit=cls._parse_decimal(mapping.get("concentration_warning_limit")),
            concentration_blocking_limit=cls._parse_decimal(mapping.get("concentration_blocking_limit")),
            minimum_liquidity_warning=cls._parse_decimal(mapping.get("minimum_liquidity_warning")),
            minimum_liquidity_blocking=cls._parse_decimal(mapping.get("minimum_liquidity_blocking")),
            minimum_marketability_score=cls._parse_decimal(mapping.get("minimum_marketability_score")),
            minimum_price_availability_score=cls._parse_decimal(mapping.get("minimum_price_availability_score")),
            required_marketability_attributes=tuple(str(item) for item in mapping.get("required_marketability_attributes", ()) or ()),
            required_encumbrance_status=tuple(str(item) for item in mapping.get("required_encumbrance_status", ()) or ()),
            policy_references=references,
            recommended_action=str(mapping.get("recommended_action")) if mapping.get("recommended_action") is not None else None,
            priority=int(mapping.get("priority", 0)),
        )

    @classmethod
    def validate_configuration_collection(cls, configs: Sequence["LiquidityPolicyConfig"]) -> None:
        seen_ids: set[str] = set()
        seen_categories: set[str] = set()
        for config in configs:
            if config.policy_id in seen_ids:
                raise InstitutionalConfigurationError("Duplicate policy ids are not allowed")
            seen_ids.add(config.policy_id)
            for category in config.issuer_categories:
                if category in seen_categories:
                    raise InstitutionalConfigurationError("Duplicate issuer categories are not allowed")
                seen_categories.add(category)
            if config.policy_references and not all(reference.identifier for reference in config.policy_references):
                raise InstitutionalConfigurationError("Policy references must include an identifier")

    @classmethod
    def _parse_date(cls, value: Any) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise InstitutionalConfigurationError("Date values must be date or ISO string")

    @classmethod
    def _parse_decimal(cls, value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, str):
            return Decimal(value)
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        raise InstitutionalConfigurationError("Decimal values must be Decimal, string, int, or float")

    def _validate(self) -> None:
        if not self.policy_id or not self.version or not self.name or not self.category:
            raise InstitutionalConfigurationError("Policy id, version, name, and category are required")
        if self.issuer_limit is not None and self.issuer_limit < 0:
            raise InstitutionalConfigurationError("Issuer limit cannot be negative")
        if self.concentration_warning_limit is not None and self.concentration_warning_limit < 0:
            raise InstitutionalConfigurationError("Concentration warning limit cannot be negative")
        if self.concentration_blocking_limit is not None and self.concentration_blocking_limit < 0:
            raise InstitutionalConfigurationError("Concentration blocking limit cannot be negative")
        if self.minimum_marketability_score is not None and self.minimum_marketability_score > Decimal("1"):
            raise InstitutionalConfigurationError("Marketability threshold cannot exceed 100%")
        if self.minimum_price_availability_score is not None and self.minimum_price_availability_score > Decimal("1"):
            raise InstitutionalConfigurationError("Price availability threshold cannot exceed 100%")
        if self.effective_date and self.expiration_date and self.expiration_date < self.effective_date:
            raise InstitutionalConfigurationError("Expiration date must be on or after effective date")
        if self.concentration_warning_limit is not None and self.concentration_blocking_limit is not None and self.concentration_blocking_limit < self.concentration_warning_limit:
            raise InstitutionalConfigurationError("Blocking concentration limit cannot be lower than warning limit")
        if self.minimum_liquidity_warning is not None and self.minimum_liquidity_blocking is not None and self.minimum_liquidity_blocking > self.minimum_liquidity_warning:
            raise InstitutionalConfigurationError("Blocking liquidity threshold cannot be above warning threshold")
        if self.policy_references and not all(isinstance(reference, PolicyReferenceConfig) for reference in self.policy_references):
            raise InstitutionalConfigurationError("Policy references must be PolicyReferenceConfig instances")

    def to_policy_reference(self) -> tuple[PolicyReference, ...]:
        return tuple(
            PolicyReference(source=reference.source, identifier=reference.identifier, url=reference.url)
            for reference in self.policy_references
        )
