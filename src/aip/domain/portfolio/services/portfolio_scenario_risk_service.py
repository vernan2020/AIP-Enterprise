from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class VerifiedScenarioRiskAsset:
    """Observed per-invested-CRC sensitivities, never inferred from display rows."""

    security_key: str
    cutoff: date
    modified_duration_years: Decimal
    dv01_crc_per_invested_crc: Decimal
    hqla_eligible_fraction: Decimal
    credit_rwa_crc_per_invested_crc: Decimal
    duration_source: str
    dv01_source: str
    hqla_source: str
    capital_source: str


@dataclass(frozen=True, slots=True)
class ScenarioRiskPolicy:
    """Approved limits for an identified policy revision and valuation date."""

    cutoff: date
    effective_date: date
    policy_version: str
    approval_reference: str
    max_modified_duration_years: Decimal | None = None
    min_hqla_fraction: Decimal | None = None
    max_absolute_dv01_crc: Decimal | None = None
    max_credit_rwa_crc: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ScenarioRiskSnapshot:
    modified_duration_years: Decimal
    dv01_crc: Decimal
    hqla_fraction: Decimal
    credit_rwa_crc: Decimal
    breached_limits: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class ScenarioRiskComparison:
    cutoff: date
    portfolio_value_crc: Decimal
    current: ScenarioRiskSnapshot
    proposed: ScenarioRiskSnapshot
    missing_limits: tuple[str, ...]
    policy_version: str
    # No claim of full ALM/regulatory compliance is made by this partial evaluator.


class PortfolioScenarioRiskService:
    """Scenario arithmetic using certified upstream sensitivities as inputs.

    Both allocations share an explicitly stated portfolio valuation base.
    This is a proposed *weight rebalance*, not a priced trade: transaction
    costs, cash settlement, tax, FX movements and actual reinvestment flows
    must be evaluated separately. DV01 retains the provider's sign convention.
    """

    @staticmethod
    def compare(
        assets: Sequence[VerifiedScenarioRiskAsset],
        current_weights: Sequence[Decimal],
        proposed_weights: Sequence[Decimal],
        *,
        cutoff: date,
        portfolio_value_crc: Decimal,
        policy: ScenarioRiskPolicy,
    ) -> ScenarioRiskComparison:
        def valid(value: Decimal) -> bool:
            return isinstance(value, Decimal) and value.is_finite()

        rows = tuple(assets)
        if not rows or len(rows) != len(current_weights) or len(rows) != len(proposed_weights):
            raise ValueError("Scenario positions and allocation weights must match")
        if not valid(portfolio_value_crc) or portfolio_value_crc <= 0:
            raise ValueError("Verified positive portfolio market value in CRC required")
        if (
            policy.cutoff != cutoff
            or policy.effective_date > cutoff
            or not policy.policy_version.strip()
            or not policy.approval_reference.strip()
        ):
            raise ValueError("Approved policy version, source and cutoff are required")
        keys = tuple(row.security_key for row in rows)
        if any(not key.strip() for key in keys) or len(set(keys)) != len(keys):
            raise ValueError("Security keys must be present and unique")

        for row in rows:
            if row.cutoff != cutoff or not all(
                source.strip()
                for source in (
                    row.duration_source,
                    row.dv01_source,
                    row.hqla_source,
                    row.capital_source,
                )
            ):
                raise ValueError("All asset sensitivities need dated audit evidence")
            if not all(
                valid(v)
                for v in (
                    row.modified_duration_years,
                    row.dv01_crc_per_invested_crc,
                    row.hqla_eligible_fraction,
                    row.credit_rwa_crc_per_invested_crc,
                )
            ):
                raise ValueError("Sensitivities must be finite Decimals")
            if (
                row.modified_duration_years < 0
                or not Decimal("0") <= row.hqla_eligible_fraction <= 1
                or row.credit_rwa_crc_per_invested_crc < 0
            ):
                raise ValueError("Duration, HQLA fraction or RWA ratio is invalid")

        definitions = (
            ("modified_duration", policy.max_modified_duration_years),
            ("hqla", policy.min_hqla_fraction),
            ("dv01", policy.max_absolute_dv01_crc),
            ("credit_rwa", policy.max_credit_rwa_crc),
        )
        if all(limit is None for _, limit in definitions):
            raise ValueError("No approved limits supplied for risk comparison")
        for key, limit in definitions:
            if limit is None:
                continue
            if not valid(limit) or limit < 0 or (key == "hqla" and limit > 1):
                raise ValueError("Risk policy limits must be finite and non-negative")
        missing = tuple(key for key, limit in definitions if limit is None)

        def validate_weights(weights: Sequence[Decimal]) -> tuple[Decimal, ...]:
            allocations = tuple(weights)
            if any(not valid(weight) or not 0 <= weight <= 1 for weight in allocations):
                raise ValueError("Scenario requires finite, long-only portfolio weights")
            if abs(sum(allocations, Decimal("0")) - 1) > Decimal("0.00000001"):
                raise ValueError("Scenario allocations must sum to 100%")
            return allocations

        def snapshot(weights: tuple[Decimal, ...]) -> ScenarioRiskSnapshot:
            duration = sum(
                (
                    weight * asset.modified_duration_years
                    for weight, asset in zip(weights, rows, strict=True)
                ),
                Decimal("0"),
            )
            dv01 = portfolio_value_crc * sum(
                (
                    weight * asset.dv01_crc_per_invested_crc
                    for weight, asset in zip(weights, rows, strict=True)
                ),
                Decimal("0"),
            )
            hqla = sum(
                (
                    weight * asset.hqla_eligible_fraction
                    for weight, asset in zip(weights, rows, strict=True)
                ),
                Decimal("0"),
            )
            rwa = portfolio_value_crc * sum(
                (
                    weight * asset.credit_rwa_crc_per_invested_crc
                    for weight, asset in zip(weights, rows, strict=True)
                ),
                Decimal("0"),
            )
            breaches: list[str] = []
            if (
                policy.max_modified_duration_years is not None
                and duration > policy.max_modified_duration_years
            ):
                breaches.append("modified_duration")
            if policy.min_hqla_fraction is not None and hqla < policy.min_hqla_fraction:
                breaches.append("hqla")
            if (
                policy.max_absolute_dv01_crc is not None
                and abs(dv01) > policy.max_absolute_dv01_crc
            ):
                breaches.append("dv01")
            if policy.max_credit_rwa_crc is not None and rwa > policy.max_credit_rwa_crc:
                breaches.append("credit_rwa")
            status = "BREACH" if breaches else "INCOMPLETE" if missing else "PASS"
            return ScenarioRiskSnapshot(
                modified_duration_years=duration,
                dv01_crc=dv01,
                hqla_fraction=hqla,
                credit_rwa_crc=rwa,
                breached_limits=tuple(breaches),
                status=status,
            )

        return ScenarioRiskComparison(
            cutoff=cutoff,
            portfolio_value_crc=portfolio_value_crc,
            current=snapshot(validate_weights(current_weights)),
            proposed=snapshot(validate_weights(proposed_weights)),
            missing_limits=missing,
            policy_version=policy.policy_version,
        )
