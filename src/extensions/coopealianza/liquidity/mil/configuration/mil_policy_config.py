from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity
from src.extensions.coopealianza.liquidity.mil.exceptions import MilConfigurationError


@dataclass(frozen=True, slots=True)
class MilIssuerConfig:
    name: str
    eligible_categories: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MilClassificationConfig:
    name: str
    excluded_prefixes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MilHaircutConfig:
    issuer_category: str | None = None
    instrument_category: str | None = None
    currency: str | None = None
    maturity_band: str | None = None
    classification: str | None = None
    haircut: Decimal | None = None


@dataclass(frozen=True, slots=True)
class MilPolicyConfig:
    """Immutable typed configuration for MIL eligibility policies."""

    policy_id: str
    version: str
    name: str
    category: str = "mil"
    enabled: bool = True
    effective_date: date | None = None
    expiration_date: date | None = None
    severity: PolicySeverity = PolicySeverity.MEDIUM
    excluded_classification_prefixes: tuple[str, ...] = field(default_factory=tuple)
    eligible_issuer_categories: tuple[str, ...] = field(default_factory=tuple)
    reserve_liquidity_treatment: str = "exclude"
    acceptable_settlement_rules: tuple[str, ...] = field(default_factory=tuple)
    valuation_freshness_limit_days: int = 1
    minimum_remaining_maturity_days: int = 0
    haircut_mappings: tuple[MilHaircutConfig, ...] = field(default_factory=tuple)
    warning_concentration_threshold: Decimal | None = None
    blocking_concentration_threshold: Decimal | None = None
    issuer_limits: tuple[tuple[str, Decimal], ...] = field(default_factory=tuple)
    currency_limits: tuple[tuple[str, Decimal], ...] = field(default_factory=tuple)
    policy_references: tuple[PolicyReference, ...] = field(default_factory=tuple)
    recommended_action: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        if self.minimum_remaining_maturity_days < 0:
            raise ValueError("Minimum remaining maturity cannot be negative")
        self._validate()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "MilPolicyConfig":
        references = tuple(
            PolicyReference(source=reference.get("source", "coopealianza"), identifier=reference.get("identifier", ""))
            if isinstance(reference, Mapping)
            else reference
            for reference in mapping.get("policy_references", ())
        )
        return cls(
            policy_id=str(mapping["policy_id"]),
            version=str(mapping["version"]),
            name=str(mapping["name"]),
            category=str(mapping.get("category", "mil")),
            enabled=bool(mapping.get("enabled", True)),
            effective_date=cls._parse_date(mapping.get("effective_date")),
            expiration_date=cls._parse_date(mapping.get("expiration_date")),
            severity=cls._parse_severity(mapping.get("severity")),
            excluded_classification_prefixes=tuple(str(item) for item in mapping.get("excluded_classification_prefixes", ()) or ()),
            eligible_issuer_categories=tuple(str(item) for item in mapping.get("eligible_issuer_categories", ()) or ()),
            reserve_liquidity_treatment=str(mapping.get("reserve_liquidity_treatment", "exclude")),
            acceptable_settlement_rules=tuple(str(item) for item in mapping.get("acceptable_settlement_rules", ()) or ()),
            valuation_freshness_limit_days=int(mapping.get("valuation_freshness_limit_days", 1)),
            minimum_remaining_maturity_days=int(mapping.get("minimum_remaining_maturity_days", 0)),
            haircut_mappings=tuple(
                MilHaircutConfig(
                    issuer_category=str(item.get("issuer_category")) if item.get("issuer_category") is not None else None,
                    instrument_category=str(item.get("instrument_category")) if item.get("instrument_category") is not None else None,
                    currency=str(item.get("currency")) if item.get("currency") is not None else None,
                    maturity_band=str(item.get("maturity_band")) if item.get("maturity_band") is not None else None,
                    classification=str(item.get("classification")) if item.get("classification") is not None else None,
                    haircut=cls._parse_decimal(item.get("haircut")),
                )
                for item in mapping.get("haircut_mappings", ()) or ()
            ),
            warning_concentration_threshold=cls._parse_decimal(mapping.get("warning_concentration_threshold")),
            blocking_concentration_threshold=cls._parse_decimal(mapping.get("blocking_concentration_threshold")),
            issuer_limits=tuple((str(key), cls._parse_decimal(value) or Decimal("0")) for key, value in mapping.get("issuer_limits", ()) or ()),
            currency_limits=tuple((str(key), cls._parse_decimal(value) or Decimal("0")) for key, value in mapping.get("currency_limits", ()) or ()),
            policy_references=references,
            recommended_action=str(mapping.get("recommended_action")) if mapping.get("recommended_action") is not None else None,
            priority=int(mapping.get("priority", 0)),
        )

    @classmethod
    def validate_configuration_collection(cls, configs: Sequence["MilPolicyConfig"]) -> None:
        seen_ids: set[str] = set()
        seen_prefixes: set[str] = set()
        seen_categories: set[str] = set()
        for config in configs:
            if config.policy_id in seen_ids:
                raise MilConfigurationError("Duplicate policy ids are not allowed")
            seen_ids.add(config.policy_id)
            for prefix in config.excluded_classification_prefixes:
                if prefix in seen_prefixes:
                    raise MilConfigurationError("Duplicate classification prefixes are not allowed")
                seen_prefixes.add(prefix)
            for category in config.eligible_issuer_categories:
                if category in seen_categories:
                    raise MilConfigurationError("Duplicate issuer categories are not allowed")
                seen_categories.add(category)
            if config.policy_references and not all(reference.identifier for reference in config.policy_references):
                raise MilConfigurationError("Policy references must include identifiers")

    @classmethod
    def _parse_date(cls, value: Any) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise MilConfigurationError("Date values must be date or ISO string")

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
        raise MilConfigurationError("Decimal values must be Decimal, string, int, or float")

    @classmethod
    def _parse_severity(cls, value: Any) -> PolicySeverity:
        if isinstance(value, PolicySeverity):
            return value
        if isinstance(value, str):
            return PolicySeverity[value]
        return PolicySeverity.MEDIUM

    def to_policy_reference(self) -> tuple[PolicyReference, ...]:
        return tuple(self.policy_references)

    def _validate(self) -> None:
        if not self.policy_id or not self.version or not self.name or not self.category:
            raise MilConfigurationError("Policy id, version, name, and category are required")
        if self.effective_date and self.expiration_date and self.expiration_date < self.effective_date:
            raise MilConfigurationError("Expiration date must be on or after effective date")
        if self.warning_concentration_threshold is not None and self.blocking_concentration_threshold is not None and self.warning_concentration_threshold > self.blocking_concentration_threshold:
            raise MilConfigurationError("Warning concentration threshold cannot exceed blocking threshold")
        if self.valuation_freshness_limit_days < 0:
            raise MilConfigurationError("Valuation freshness limit cannot be negative")
        for selection in self.haircut_mappings:
            if selection.haircut is None:
                continue
            if selection.haircut < 0:
                raise MilConfigurationError("Haircut cannot be negative")
            if selection.haircut > Decimal("1"):
                raise MilConfigurationError("Haircut cannot exceed 100%")
        for _, limit in self.issuer_limits:
            if limit < 0:
                raise MilConfigurationError("Issuer limits cannot be negative")
        for _, limit in self.currency_limits:
            if limit < 0:
                raise MilConfigurationError("Currency limits cannot be negative")
        if self.policy_references and not all(isinstance(reference, PolicyReference) for reference in self.policy_references):
            raise MilConfigurationError("Policy references must be PolicyReference instances")
        if self.reserve_liquidity_treatment not in {"exclude", "conditional", "allow"}:
            raise MilConfigurationError("Reserve liquidity treatment must be exclude, conditional, or allow")
        if self.warning_concentration_threshold is not None and self.warning_concentration_threshold < 0:
            raise MilConfigurationError("Warning concentration threshold cannot be negative")
        if self.blocking_concentration_threshold is not None and self.blocking_concentration_threshold < 0:
            raise MilConfigurationError("Blocking concentration threshold cannot be negative")
        if self.enabled is False:
            return
