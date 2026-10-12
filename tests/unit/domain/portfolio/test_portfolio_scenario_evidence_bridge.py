from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    ExposureClass,
)
from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    VerifiedCapitalPosition,
)
from aip.domain.portfolio.services.portfolio_scenario_evidence_bridge import (
    PortfolioScenarioEvidenceBridge,
    VerifiedPositionMarketRisk,
)
from aip.domain.portfolio.services.portfolio_scenario_risk_service import ScenarioRiskPolicy

CUTOFF = date(2026, 10, 2)


def _positions() -> tuple[VerifiedCapitalPosition, ...]:
    def row(
        key: str, issuer: str, invested: str, exposure: str, cls: ExposureClass
    ) -> VerifiedCapitalPosition:
        return VerifiedCapitalPosition(
            position_key=key,
            isin=f"ISIN-{key}",
            issuer=issuer,
            currency="CRC",
            cutoff=CUTOFF,
            invested_amount_crc=Decimal(invested),
            regulatory_exposure_crc=Decimal(exposure),
            annual_net_yield=Decimal("0.05"),
            exposure_class=cls,
            classification_effective_date=date(2026, 9, 30),
            invested_amount_source=f"confirmed acquisition {key}",
            regulatory_exposure_source=f"confirmed regulatory base {key}",
            net_yield_source=f"confirmed net return {key}",
            classification_source=f"approved SUGEF bucket {key}",
        )

    return (
        row("A", "Gobierno", "1000", "800", ExposureClass.GOVERNMENT_CRC),
        row("B", "Private X", "300", "160", ExposureClass.UNRATED),
    )


def _risks() -> tuple[VerifiedPositionMarketRisk, ...]:
    def row(
        key: str, market: str, duration: str, dv01: str, hqla: str
    ) -> VerifiedPositionMarketRisk:
        return VerifiedPositionMarketRisk(
            position_key=key,
            cutoff=CUTOFF,
            market_value_crc=Decimal(market),
            modified_duration_years=Decimal(duration),
            dv01_crc=Decimal(dv01),
            eligible_hqla_value_crc=Decimal(hqla),
            market_value_source=f"verified vector valuation {key}",
            duration_source=f"verified duration calculation {key}",
            dv01_source=f"verified DV01 calculation {key}",
            hqla_source=f"verified HQLA determination {key}",
        )

    return (row("B", "200", "5", "0.04", "0"), row("A", "800", "1", "0.08", "720"))


def _policy() -> ScenarioRiskPolicy:
    return ScenarioRiskPolicy(
        cutoff=CUTOFF,
        effective_date=date(2026, 9, 30),
        policy_version="APPROVED-2026",
        approval_reference="policy signed by board",
        max_modified_duration_years=Decimal("3"),
        min_hqla_fraction=Decimal("0.50"),
        max_absolute_dv01_crc=Decimal("0.16"),
        max_credit_rwa_crc=Decimal("400"),
    )


def _compare(*, positions=None, risks=None, proposed=None, total=Decimal("1000"), source="vector"):
    return PortfolioScenarioEvidenceBridge.compare(
        _positions() if positions is None else positions,
        _risks() if risks is None else risks,
        {"A": Decimal("0.2"), "B": Decimal("0.8")} if proposed is None else proposed,
        cutoff=CUTOFF,
        portfolio_market_value_crc=total,
        portfolio_valuation_source=source,
        policy=_policy(),
    )


def test_reconciles_capital_apr_separate_from_market_weight_basis() -> None:
    result = _compare()
    assert result.position_keys == ("A", "B")
    assert result.current_weights == (Decimal("0.8"), Decimal("0.2"))
    assert result.regulatory_exposure_crc == Decimal("960")
    assert result.current_credit_rwa_crc == Decimal("160")
    assert result.comparison.current.credit_rwa_crc == Decimal("160")
    assert result.comparison.proposed.credit_rwa_crc == Decimal("640")
    assert result.comparison.current.modified_duration_years == Decimal("1.8")
    assert result.comparison.proposed.modified_duration_years == Decimal("4.2")
    assert result.comparison.current.dv01_crc == Decimal("0.120")
    assert result.comparison.proposed.dv01_crc == Decimal("0.180")
    assert result.comparison.current.hqla_fraction == Decimal("0.72")
    assert result.comparison.proposed.hqla_fraction == Decimal("0.18")
    assert result.comparison.current.status == "PASS"
    assert set(result.comparison.proposed.breached_limits) == {
        "modified_duration",
        "hqla",
        "dv01",
        "credit_rwa",
    }
    assert result.comparison.proposed.status == "BREACH"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"market_value_crc": Decimal("-5")}, "Invalid market"),
        ({"eligible_hqla_value_crc": Decimal("300")}, "Invalid market"),
        ({"dv01_crc": Decimal("NaN")}, "finite"),
        ({"duration_source": ""}, "source references"),
        ({"cutoff": date(2026, 10, 3)}, "cutoff"),
    ],
)
def test_rejects_bad_valuation_evidence(changes: dict[str, object], message: str) -> None:
    rows = _risks()
    with pytest.raises(ValueError, match=message):
        _compare(risks=(replace(rows[0], **changes), rows[1]))


def test_rejects_incomplete_join_or_ambiguous_lots() -> None:
    rows = _risks()
    with pytest.raises(ValueError, match="match every"):
        _compare(risks=rows[:1])
    with pytest.raises(ValueError, match="match every"):
        _compare(risks=(rows[0], rows[0]))
    with pytest.raises(ValueError, match="every position"):
        _compare(proposed={"A": Decimal("1")})


def test_rejects_unreconciled_total_and_missing_source() -> None:
    with pytest.raises(ValueError, match="reconcile"):
        _compare(total=Decimal("999"))
    with pytest.raises(ValueError, match="audit source"):
        _compare(source="")


def test_regulatory_classification_provenance_cannot_be_bypassed() -> None:
    positions = _positions()
    with pytest.raises(ValueError, match="source references"):
        _compare(
            positions=(
                positions[0],
                replace(positions[1], regulatory_exposure_source=""),
            )
        )


def test_same_issuer_multiple_lots_are_kept_separate() -> None:
    positions = _positions()
    other = replace(
        positions[1],
        position_key="C",
        isin="ISIN-C",
        regulatory_exposure_crc=Decimal("0"),
    )
    risks = _risks()
    third = replace(
        risks[0],
        position_key="C",
        market_value_crc=Decimal("100"),
        dv01_crc=Decimal("0"),
        eligible_hqla_value_crc=Decimal("0"),
    )
    second = replace(
        risks[0],
        market_value_crc=Decimal("100"),
        dv01_crc=Decimal("0.02"),
    )
    result = _compare(
        positions=(positions[0], positions[1], other),
        risks=(risks[1], second, third),
        proposed={
            "A": Decimal("0.5"),
            "B": Decimal("0.25"),
            "C": Decimal("0.25"),
        },
    )
    assert result.position_keys == ("A", "B", "C")
    assert result.comparison.current.credit_rwa_crc == Decimal("160")
