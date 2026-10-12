from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    ExposureClass,
    PortfolioCapitalEvidenceService,
    VerifiedCapitalPosition,
)

CUTOFF = date(2026, 10, 2)


def _verified(**changes) -> VerifiedCapitalPosition:
    record = VerifiedCapitalPosition(
        position_key="lot-001",
        isin="CRTEST000001",
        issuer="Gobierno",
        currency="USD",
        cutoff=CUTOFF,
        invested_amount_crc=Decimal("100"),
        regulatory_exposure_crc=Decimal("120"),
        annual_net_yield=Decimal("0.08"),
        exposure_class=ExposureClass.GOVERNMENT_USD,
        classification_effective_date=date(2026, 9, 30),
        invested_amount_source="portfolio book / lot-001",
        regulatory_exposure_source="verified regulatory basis / lot-001",
        net_yield_source="approved net yield model / 2026-10-02",
        classification_source="SUGEF rating master / 2026-09-30",
        fx_translation_source="BCCR conversion / 2026-10-02",
    )
    return replace(record, **changes)


def test_evidence_bridge_uses_verified_regulatory_exposure() -> None:
    result = PortfolioCapitalEvidenceService.evaluate(
        (_verified(),), cutoff=CUTOFF, annual_cost_of_equity=Decimal("0.12")
    )
    assert result.portfolio.total_credit_rwa_crc == Decimal("90")
    assert result.equivalent_rates[0].required_capital_crc == Decimal("14.4000")
    assert result.equivalent_rates[0].annual_equity_charge_crc == Decimal("1.728000")
    assert result.equivalent_rates[0].equivalent_yield_at_reference_risk_weight == Decimal(
        "0.06272000"
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"cutoff": date(2026, 10, 1)}, "cutoff"),
        ({"classification_effective_date": date(2026, 10, 3)}, "Future-dated"),
        ({"regulatory_exposure_crc": Decimal("NaN")}, "finite"),
        ({"regulatory_exposure_crc": Decimal("-1")}, "non-negative"),
        ({"invested_amount_source": ""}, "source"),
        ({"fx_translation_source": ""}, "FX"),
        ({"exposure_class": ExposureClass.GOVERNMENT_CRC}, "requires CRC"),
    ],
)
def test_evidence_fails_closed(changes: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        PortfolioCapitalEvidenceService.evaluate(
            (_verified(**changes),), cutoff=CUTOFF, annual_cost_of_equity=Decimal("0.12")
        )


def test_multiple_lots_require_distinct_keys() -> None:
    with pytest.raises(ValueError, match="unique"):
        PortfolioCapitalEvidenceService.validate((_verified(), _verified()), cutoff=CUTOFF)
    result = PortfolioCapitalEvidenceService.evaluate(
        (_verified(), _verified(position_key="lot-002")),
        cutoff=CUTOFF,
        annual_cost_of_equity=Decimal("0"),
    )
    assert len(result.portfolio.items) == 2
    assert result.annual_equity_charge_crc == Decimal("0")


def test_no_default_equity_cost_and_no_source_fallback() -> None:
    with pytest.raises(TypeError, match="annual_cost_of_equity"):
        PortfolioCapitalEvidenceService.evaluate((_verified(),), cutoff=CUTOFF)
    with pytest.raises(ValueError, match="source"):
        PortfolioCapitalEvidenceService.validate(
            (_verified(classification_source=""),), cutoff=CUTOFF
        )
