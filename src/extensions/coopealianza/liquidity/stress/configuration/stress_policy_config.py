from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from src.extensions.coopealianza.liquidity.stress.exceptions import StressConfigurationError


@dataclass(frozen=True, slots=True)
class StressScenarioConfig:
    """Immutable scenario definition for a stress test."""

    scenario_id: str
    name: str
    scenario_type: str
    severity: Decimal = Decimal("0")
    rate_shift: Decimal = Decimal("0")
    liquidity_factor: Decimal = Decimal("0")
    concentration_factor: Decimal = Decimal("0")
    runoff_rate: Decimal = Decimal("0")
    withdrawal_rate: Decimal = Decimal("0")
    collateral_multiplier: Decimal = Decimal("1")
    market_value_multiplier: Decimal = Decimal("1")
    policy_references: tuple[str, ...] = field(default_factory=tuple)
    affected_assets: tuple[str, ...] = field(default_factory=tuple)
    affected_buckets: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    combined_scenario_ids: tuple[str, ...] = field(default_factory=tuple)
    effective_date: date | None = None
    expiration_date: date | None = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.scenario_id or not self.name or not self.scenario_type:
            raise StressConfigurationError("Scenario id, name, and type are required")
        if self.scenario_type not in {
            "parallel_shift",
            "twist",
            "butterfly",
            "historical",
            "hypothetical",
            "deposit_runoff",
            "wholesale_funding_shock",
            "collateral_haircut",
            "market_liquidity_deterioration",
            "combined",
        }:
            raise StressConfigurationError("Scenario type is not supported")
        if self.scenario_type == "combined" and not self.combined_scenario_ids:
            raise StressConfigurationError("Combined scenarios require scenario references")
        if not self.policy_references:
            raise StressConfigurationError("Scenario policy references are required")
        for value in (
            self.severity,
            self.rate_shift,
            self.liquidity_factor,
            self.concentration_factor,
            self.runoff_rate,
            self.withdrawal_rate,
            self.collateral_multiplier,
            self.market_value_multiplier,
        ):
            if value < 0 or value > Decimal("1"):
                raise StressConfigurationError("Scenario percentages must stay within 0% and 100%")
        if (
            self.effective_date
            and self.expiration_date
            and self.expiration_date < self.effective_date
        ):
            raise StressConfigurationError(
                "Scenario expiration date must be on or after effective date"
            )


@dataclass(frozen=True, slots=True)
class StressPolicyConfig:
    """Immutable typed configuration for liquidity stress scenarios."""

    policy_id: str
    version: str
    name: str
    category: str = "stress"
    enabled: bool = True
    effective_date: date | None = None
    expiration_date: date | None = None
    scenarios: tuple[StressScenarioConfig, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self._validate()

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "StressPolicyConfig":
        scenarios = tuple(
            StressScenarioConfig(
                scenario_id=str(item.get("scenario_id") or item.get("id") or item.get("name", "")),
                name=str(item.get("name", "")),
                scenario_type=str(item.get("scenario_type", "")),
                severity=Decimal(str(item.get("severity", "0"))),
                rate_shift=Decimal(str(item.get("rate_shift", "0"))),
                liquidity_factor=Decimal(str(item.get("liquidity_factor", "0"))),
                concentration_factor=Decimal(str(item.get("concentration_factor", "0"))),
                runoff_rate=Decimal(str(item.get("runoff_rate", "0"))),
                withdrawal_rate=Decimal(str(item.get("withdrawal_rate", "0"))),
                collateral_multiplier=Decimal(str(item.get("collateral_multiplier", "1"))),
                market_value_multiplier=Decimal(str(item.get("market_value_multiplier", "1"))),
                policy_references=tuple(
                    str(reference) for reference in item.get("policy_references", ()) or ()
                ),
                affected_assets=tuple(
                    str(asset) for asset in item.get("affected_assets", ()) or ()
                ),
                affected_buckets=tuple(
                    str(bucket) for bucket in item.get("affected_buckets", ()) or ()
                ),
                assumptions=tuple(
                    str(assumption) for assumption in item.get("assumptions", ()) or ()
                ),
                warnings=tuple(str(warning) for warning in item.get("warnings", ()) or ()),
                combined_scenario_ids=tuple(
                    str(reference) for reference in item.get("combined_scenario_ids", ()) or ()
                ),
                effective_date=cls._parse_date(item.get("effective_date")),
                expiration_date=cls._parse_date(item.get("expiration_date")),
            )
            for item in mapping.get("scenarios", ()) or ()
        )
        return cls(
            policy_id=str(mapping["policy_id"]),
            version=str(mapping["version"]),
            name=str(mapping["name"]),
            category=str(mapping.get("category", "stress")),
            enabled=bool(mapping.get("enabled", True)),
            effective_date=cls._parse_date(mapping.get("effective_date")),
            expiration_date=cls._parse_date(mapping.get("expiration_date")),
            scenarios=scenarios,
        )

    @classmethod
    def _parse_date(cls, value: Any) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise StressConfigurationError("Date values must be date or ISO string")

    def _validate(self) -> None:
        if not self.policy_id or not self.version or not self.name or not self.category:
            raise StressConfigurationError("Policy id, version, name, and category are required")
        if (
            self.effective_date
            and self.expiration_date
            and self.expiration_date < self.effective_date
        ):
            raise StressConfigurationError(
                "Policy expiration date must be on or after effective date"
            )
        seen_ids: set[str] = set()
        for scenario in self.scenarios:
            if scenario.scenario_id in seen_ids:
                raise StressConfigurationError("Duplicate scenario ids are not allowed")
            seen_ids.add(scenario.scenario_id)
