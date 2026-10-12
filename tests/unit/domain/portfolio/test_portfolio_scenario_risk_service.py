from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_scenario_risk_service import (
    PortfolioScenarioRiskService,
    ScenarioRiskPolicy,
    VerifiedScenarioRiskAsset,
)

CUTOFF = date(2026, 10, 2)


def _assets() -> tuple[VerifiedScenarioRiskAsset, ...]:
    def row(key: str, duration: str, dv01: str, hqla: str, rwa: str) -> VerifiedScenarioRiskAsset:
        return VerifiedScenarioRiskAsset(
            security_key=key,
            cutoff=CUTOFF,
            modified_duration_years=Decimal(duration),
            dv01_crc_per_invested_crc=Decimal(dv01),
            hqla_eligible_fraction=Decimal(hqla),
            credit_rwa_crc_per_invested_crc=Decimal(rwa),
            duration_source="approved duration engine on cutoff",
            dv01_source="approved DV01 engine on cutoff",
            hqla_source="approved HQLA master on cutoff",
            capital_source="approved regulatory exposure and weight on cutoff",
        )
    return (row("A", "1", "0.0001", "1", "0"), row("B", "5", "0.0005", "0.8", "0.75"))


def _policy(**changes: object) -> ScenarioRiskPolicy:
    return replace(
        ScenarioRiskPolicy(
            cutoff=CUTOFF,
            effective_date=date(2026, 9, 30),
            policy_version="POLICY-APPROVED-2026",
            approval_reference="approved investment limits for cutoff",
            max_modified_duration_years=Decimal("3"),
            min_hqla_fraction=Decimal("0.90"),
            max_absolute_dv01_crc=Decimal("300"),
            max_credit_rwa_crc=Decimal("400000"),
        ),
        **changes,
    )


def _compare(*, assets=None, policy=None, current=None, proposed=None):
    return PortfolioScenarioRiskService.compare(
        _assets() if assets is None else assets,
        (Decimal("0.8"), Decimal("0.2")) if current is None else current,
        (Decimal("0.2"), Decimal("0.8")) if proposed is None else proposed,
        cutoff=CUTOFF,
        portfolio_value_crc=Decimal("1000000"),
        policy=_policy() if policy is None else policy,
    )


def test_rebalance_compares_all_four_risks_without_repricing_bonds() -> None:
    result = _compare()
    assert result.current.status == "PASS"
    assert result.current.modified_duration_years == Decimal("1.8")
    assert result.current.dv01_crc == Decimal("180.000000")
    assert result.current.hqla_fraction == Decimal("0.96")
    assert result.current.credit_rwa_crc == Decimal("150000.000")
    assert result.proposed.modified_duration_years == Decimal("4.2")
    assert result.proposed.dv01_crc == Decimal("420.000000")
    assert result.proposed.hqla_fraction == Decimal("0.84")
    assert result.proposed.credit_rwa_crc == Decimal("600000.000")
    assert result.proposed.status == "BREACH"
    assert set(result.proposed.breached_limits) == {
        "modified_duration", "hqla", "dv01", "credit_rwa"
    }


def test_missing_policy_limits_do_not_return_a_false_pass() -> None:
    policy = _policy(max_absolute_dv01_crc=None, max_credit_rwa_crc=None)
    result = _compare(policy=policy, proposed=(Decimal("0.8"), Decimal("0.2")))
    assert result.current.status == "INCOMPLETE"
    assert result.proposed.status == "INCOMPLETE"
    assert result.missing_limits == ("dv01", "credit_rwa")


@pytest.mark.parametrize(
    ("asset_changes", "message"),
    [
        ({"duration_source": ""}, "audit evidence"),
        ({"hqla_eligible_fraction": Decimal("1.1")}, "invalid"),
        ({"dv01_crc_per_invested_crc": Decimal("NaN")}, "finite"),
        ({"credit_rwa_crc_per_invested_crc": Decimal("-1")}, "invalid"),
        ({"cutoff": date(2026, 10, 3)}, "audit evidence"),
    ],
)
def test_asset_evidence_is_required(asset_changes: dict[str, object], message: str) -> None:
    rows = _assets()
    with pytest.raises(ValueError, match=message):
        _compare(assets=(replace(rows[0], **asset_changes), rows[1]))


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ((Decimal("0.9"), Decimal("0.2")), "100%"),
        ((Decimal("-0.1"), Decimal("1.1")), "long-only"),
        ((Decimal("NaN"), Decimal("0.1")), "long-only"),
    ],
)
def test_unbalanced_or_short_weights_fail_closed(weights, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _compare(proposed=weights)


def test_unapproved_or_future_dated_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="Approved policy"):
        _compare(policy=_policy(approval_reference=""))
    with pytest.raises(ValueError, match="Approved policy"):
        _compare(policy=_policy(effective_date=date(2026, 10, 3)))


def test_signed_dv01_is_preserved_and_absolute_limit_applied() -> None:
    rows = _assets()
    hedged = (replace(rows[0], dv01_crc_per_invested_crc=Decimal("-0.0005")), rows[1])
    result = _compare(
        assets=hedged,
        proposed=(Decimal("1"), Decimal("0")),
        policy=_policy(max_absolute_dv01_crc=Decimal("200")),
    )
    assert result.proposed.dv01_crc == Decimal("-500.000000")
    assert "dv01" in result.proposed.breached_limits
