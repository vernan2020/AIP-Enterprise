from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_capital_breakdown_service import (
    PortfolioCapitalBreakdownService,
)
from aip.domain.portfolio.services.portfolio_capital_consumption_service import ExposureClass
from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    VerifiedCapitalPosition,
)

CUTOFF = date(2026, 10, 2)


def _crc() -> VerifiedCapitalPosition:
    return VerifiedCapitalPosition(
        position_key="lot-crc",
        isin="CR-TEST-01",
        issuer="Gobierno",
        currency="CRC",
        cutoff=CUTOFF,
        invested_amount_crc=Decimal("100"),
        regulatory_exposure_crc=Decimal("100"),
        annual_net_yield=Decimal("0.04"),
        exposure_class=ExposureClass.GOVERNMENT_CRC,
        classification_effective_date=CUTOFF,
        invested_amount_source="unit fixture: verified book base",
        regulatory_exposure_source="unit fixture: regulatory base",
        net_yield_source="unit fixture: net return",
        classification_source="unit fixture: sovereign CRC rule",
    )


def _usd() -> VerifiedCapitalPosition:
    return replace(
        _crc(),
        position_key="lot-usd",
        isin="US-TEST-02",
        currency="USD",
        invested_amount_crc=Decimal("200"),
        regulatory_exposure_crc=Decimal("200"),
        annual_net_yield=Decimal("0.08"),
        exposure_class=ExposureClass.GOVERNMENT_USD,
        classification_source="unit fixture: sovereign USD rule",
        fx_translation_source="unit fixture: BCCR FX conversion reference",
    )


def test_breakdown_reconciles_issuer_currency_and_classification() -> None:
    result = PortfolioCapitalBreakdownService.calculate(
        (_crc(), _usd()), cutoff=CUTOFF, annual_cost_of_equity=Decimal("0.10")
    )
    assert result.total_positions == 2
    assert result.total_invested_crc == Decimal("300")
    assert result.total_regulatory_exposure_crc == Decimal("300")
    assert result.total_credit_rwa_crc == Decimal("150")
    assert result.target_equity_crc == Decimal("24.000")
    assert result.annual_equity_charge_crc == Decimal("2.40000")
    assert result.weighted_net_yield_before_equity_cost == Decimal("20") / Decimal("300")
    assert result.weighted_net_yield_after_equity_cost == Decimal("17.6") / Decimal("300")

    assert len(result.by_issuer) == 1
    assert result.by_issuer[0].label == "Gobierno"
    assert result.by_issuer[0].position_count == 2
    assert result.by_issuer[0].credit_rwa_crc == Decimal("150")
    assert len(result.by_issuer[0].classification_sources) == 2

    assert tuple(item.label for item in result.by_currency) == ("CRC", "USD")
    assert result.by_currency[0].annual_equity_charge_crc == Decimal("0")
    assert result.by_currency[1].annual_equity_charge_crc == Decimal("2.4")
    assert tuple(item.label for item in result.by_exposure_class) == (
        "GOVERNMENT_CRC",
        "GOVERNMENT_USD",
    )
    for grouping in (result.by_issuer, result.by_currency, result.by_exposure_class):
        assert sum((group.invested_amount_crc for group in grouping), Decimal("0")) == (
            result.total_invested_crc
        )
        assert sum((group.credit_rwa_crc for group in grouping), Decimal("0")) == (
            result.total_credit_rwa_crc
        )
        assert sum((group.annual_equity_charge_crc for group in grouping), Decimal("0")) == (
            result.annual_equity_charge_crc
        )


def test_editable_equity_cost_and_separate_regulatory_exposure() -> None:
    usd = replace(_usd(), regulatory_exposure_crc=Decimal("240"))
    low = PortfolioCapitalBreakdownService.calculate(
        (_crc(), usd), cutoff=CUTOFF, annual_cost_of_equity=Decimal("0.10")
    )
    high = PortfolioCapitalBreakdownService.calculate(
        (_crc(), usd), cutoff=CUTOFF, annual_cost_of_equity=Decimal("0.20")
    )
    assert low.total_credit_rwa_crc == Decimal("180")
    assert low.target_equity_crc == Decimal("28.800")
    assert low.annual_equity_charge_crc == Decimal("2.88000")
    assert high.annual_equity_charge_crc == Decimal("5.76000")
    assert high.weighted_net_yield_after_equity_cost < (
        low.weighted_net_yield_after_equity_cost
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"cutoff": date(2026, 10, 1)}, "cutoff"),
        ({"classification_source": ""}, "source"),
        ({"invested_amount_crc": Decimal("0")}, "positive"),
        ({"exposure_class": ExposureClass.GOVERNMENT_USD}, "requires USD"),
    ],
)
def test_breakdown_rejects_invalid_evidence(changes: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        PortfolioCapitalBreakdownService.calculate(
            (replace(_crc(), **changes),),
            cutoff=CUTOFF,
            annual_cost_of_equity=Decimal("0.10"),
        )
