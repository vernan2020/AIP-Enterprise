from __future__ import annotations

from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from aip.domain.portfolio.services.markowitz_institutional_policy_compiler import (
    InvestmentPolicySnapshot,
    MarkowitzInstitutionalPolicyCompiler,
    VerifiedPolicyGroupRule,
    VerifiedPolicyHolding,
)
from aip.domain.portfolio.services.markowitz_optimizer import MarkowitzOptimizer

CUTOFF = date(2026, 10, 2)


def _policy() -> InvestmentPolicySnapshot:
    return InvestmentPolicySnapshot(
        cutoff=CUTOFF,
        effective_date=date(2026, 1, 1),
        policy_version="APPROVED-POLICY-2026",
        approval_reference="ALCO approved snapshot by cutoff",
        group_rules=(
            VerifiedPolicyGroupRule("gov-bccr", 0.90),
            VerifiedPolicyGroupRule("private", 0.10, 0.03),
            VerifiedPolicyGroupRule("under-1-year", 0.37),
            VerifiedPolicyGroupRule("one-to-five-years", 0.48),
            VerifiedPolicyGroupRule("over-five-years", 0.30),
        ),
    )


def _holding(key: str, issuer: str, *groups: str) -> VerifiedPolicyHolding:
    return VerifiedPolicyHolding(
        security_key=key,
        issuer=issuer,
        policy_groups=groups,
        classification_source=f"approved security master: {key}",
        cutoff=CUTOFF,
    )


def test_policy_compiler_builds_overlapping_issuer_category_and_tenor_limits() -> None:
    assets = (
        _holding("G1", "Gobierno", "gov-bccr", "one-to-five-years"),
        _holding("B1", "BCCR", "gov-bccr", "under-1-year"),
        _holding("P1", "Empresa X", "private", "one-to-five-years"),
        _holding("P2", "Empresa X", "private", "over-five-years"),
    )
    limits = MarkowitzInstitutionalPolicyCompiler.compile(assets, _policy(), cutoff=CUTOFF)
    groups = {item.name: item for item in limits.group_limits}
    assert groups["gov-bccr"].asset_indices == (0, 1)
    assert groups["gov-bccr"].maximum_weight == 0.90
    assert groups["private"].asset_indices == (2, 3)
    assert groups["private :: Empresa X"].asset_indices == (2, 3)
    assert groups["private :: Empresa X"].maximum_weight == 0.03
    assert groups["over-five-years"].maximum_weight == 0.30
    assert limits.minimum_weights == (0.0,) * 4


def test_compiled_infeasible_policy_is_detected_before_mean_variance() -> None:
    assets = (
        _holding("G1", "Gobierno", "gov-bccr", "one-to-five-years"),
        _holding("P1", "Empresa A", "private", "under-1-year"),
        _holding("P2", "Empresa B", "private", "over-five-years"),
    )
    limits = MarkowitzInstitutionalPolicyCompiler.compile(assets, _policy(), cutoff=CUTOFF)
    historical = np.column_stack((np.full(40, 0.001), np.full(40, 0.002), np.full(40, 0.003)))
    with pytest.raises(ValueError, match="infeasible"):
        MarkowitzOptimizer.optimize(("G1", "P1", "P2"), historical, limits)


@pytest.mark.parametrize(
    ("holdings", "policy_changes", "message"),
    [
        ((_holding("A", "Issuer", "unrecognized"), _holding("B", "X", "private")), {}, "tags"),
        ((_holding("A", "Issuer", "private"), _holding("A", "X", "private")), {}, "Duplicate"),
        (
            (_holding("A", "Issuer", "private"), _holding("B", "X", "private")),
            {"approval_reference": ""},
            "approval",
        ),
        (
            (_holding("A", "Issuer", "private"), _holding("B", "X", "private")),
            {"effective_date": date(2026, 10, 3)},
            "cutoff",
        ),
    ],
)
def test_policy_compiler_rejects_unverified_or_ambiguous_inputs(
    holdings: tuple[VerifiedPolicyHolding, ...],
    policy_changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        MarkowitzInstitutionalPolicyCompiler.compile(
            holdings, replace(_policy(), **policy_changes), cutoff=CUTOFF
        )
