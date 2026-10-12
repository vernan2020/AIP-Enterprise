from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Sequence

from aip.domain.portfolio.services.markowitz_optimizer import (
    MarkowitzConstraints,
    MarkowitzGroupLimit,
)


@dataclass(frozen=True, slots=True)
class VerifiedPolicyGroupRule:
    """Approved investment policy cap; no institution-wide default is assumed."""

    group_key: str
    maximum_fraction: float
    maximum_per_issuer_fraction: float | None = None


@dataclass(frozen=True, slots=True)
class VerifiedPolicyHolding:
    security_key: str
    issuer: str
    policy_groups: tuple[str, ...]
    classification_source: str
    cutoff: date


@dataclass(frozen=True, slots=True)
class InvestmentPolicySnapshot:
    """Audited concentration limits applicable at the investment decision cutoff."""

    cutoff: date
    effective_date: date
    policy_version: str
    approval_reference: str
    group_rules: tuple[VerifiedPolicyGroupRule, ...]


class MarkowitzInstitutionalPolicyCompiler:
    """Compile overlapping category/issuer/tenor caps into Markowitz group limits.

    This handles only linear concentration and tagged maturity-bucket caps.
    Duration, HQLA and regulatory capital limits require separate controls;
    the result must never be labelled full institutional-policy compliance.
    """

    @staticmethod
    def compile(
        assets: Sequence[VerifiedPolicyHolding],
        policy: InvestmentPolicySnapshot,
        *,
        cutoff: date,
    ) -> MarkowitzConstraints:
        records = tuple(assets)
        if len(records) < 2:
            raise ValueError("At least two audited securities are required")
        if policy.cutoff != cutoff or policy.effective_date > cutoff:
            raise ValueError("Policy cutoff or effective date does not match valuation")
        if not policy.policy_version.strip() or not policy.approval_reference.strip():
            raise ValueError("Policy version and approval evidence are required")
        if not policy.group_rules:
            raise ValueError("At least one approved policy limit is required")

        rules = policy.group_rules
        rule_keys = tuple(rule.group_key for rule in rules)
        if any(not key.strip() for key in rule_keys) or len(set(rule_keys)) != len(rule_keys):
            raise ValueError("Policy group keys must be nonblank and unique")
        for rule in rules:
            if not isfinite(rule.maximum_fraction) or not 0 <= rule.maximum_fraction <= 1:
                raise ValueError("Invalid approved policy concentration cap")
            issuer_cap = rule.maximum_per_issuer_fraction
            if issuer_cap is not None and (
                not isfinite(issuer_cap) or not 0 <= issuer_cap <= rule.maximum_fraction
            ):
                raise ValueError("Invalid approved issuer concentration cap")

        security_keys = tuple(asset.security_key for asset in records)
        if any(not key.strip() for key in security_keys) or len(set(security_keys)) != len(
            security_keys
        ):
            raise ValueError("Duplicate or missing security keys in policy universe")
        for asset in records:
            if asset.cutoff != cutoff or not asset.issuer.strip():
                raise ValueError("Investment position issuer/cutoff is unverified")
            if not asset.classification_source.strip():
                raise ValueError("Investment policy classification needs audit evidence")
            if (
                not asset.policy_groups
                or len(set(asset.policy_groups)) != len(asset.policy_groups)
                or any(group not in rule_keys for group in asset.policy_groups)
            ):
                raise ValueError("An investment has missing or unapproved policy group tags")

        limits: list[MarkowitzGroupLimit] = []
        for rule in rules:
            indices = tuple(
                index
                for index, asset in enumerate(records)
                if rule.group_key in asset.policy_groups
            )
            if not indices:
                continue
            limits.append(
                MarkowitzGroupLimit(
                    name=rule.group_key,
                    asset_indices=indices,
                    maximum_weight=rule.maximum_fraction,
                )
            )
            if rule.maximum_per_issuer_fraction is None:
                continue
            issuers = tuple(dict.fromkeys(records[index].issuer for index in indices))
            for issuer in issuers:
                issuer_indices = tuple(
                    index for index in indices if records[index].issuer == issuer
                )
                limits.append(
                    MarkowitzGroupLimit(
                        name=f"{rule.group_key} :: {issuer}",
                        asset_indices=issuer_indices,
                        maximum_weight=rule.maximum_per_issuer_fraction,
                    )
                )

        constraints = MarkowitzConstraints(
            minimum_weights=(0.0,) * len(records),
            maximum_weights=(1.0,) * len(records),
            group_limits=tuple(limits),
        )
        constraints.validate(len(records))
        return constraints
