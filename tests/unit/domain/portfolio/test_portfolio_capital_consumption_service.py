from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    CapitalExposure,
    ExposureClass,
    PortfolioCapitalConsumptionService,
)


def exposure(key, issuer, currency, balance, classification):
    return CapitalExposure(
        security_key=key,
        issuer=issuer,
        currency=currency,
        regulatory_exposure_crc=Decimal(balance),
        exposure_class=classification,
        classification_source="Approved classification for unit test",
    )


def test_sugef_investment_rwa_and_weighted_average() -> None:
    result = PortfolioCapitalConsumptionService.evaluate(
        (
            exposure("B1", "BCCR", "CRC", "100", ExposureClass.BCCR_CRC),
            exposure("G1", "Gobierno", "CRC", "200", ExposureClass.GOVERNMENT_CRC),
            exposure("C1", "Coocique", "CRC", "30", ExposureClass.UNRATED),
            exposure("R1", "Rated issuer", "CRC", "40", ExposureClass.RATED_4),
        )
    )
    assert result.total_regulatory_exposure_crc == Decimal("370")
    assert result.total_credit_rwa_crc == Decimal("60")
    assert result.weighted_average_risk_weight == Decimal("60") / Decimal("370")
    assert result.items[2].risk_weight == Decimal("1")
    assert result.items[3].risk_weight == Decimal("0.75")


def test_foreign_currency_sovereign_cannot_use_crc_exemption() -> None:
    with pytest.raises(ValueError, match="requires CRC"):
        PortfolioCapitalConsumptionService.evaluate(
            (exposure("B1", "BCCR", "USD", "100", ExposureClass.BCCR_CRC),)
        )


def test_missing_classification_source_is_not_silently_accepted() -> None:
    item = CapitalExposure(
        security_key="C1",
        issuer="Coocique",
        currency="CRC",
        regulatory_exposure_crc=Decimal("1"),
        exposure_class=ExposureClass.UNRATED,
        classification_source="",
    )
    with pytest.raises(ValueError, match="Classification source"):
        PortfolioCapitalConsumptionService.evaluate((item,))


def test_negative_or_nonfinite_exposure_is_rejected() -> None:
    for value in ("-1", "NaN"):
        with pytest.raises(ValueError, match="finite and non-negative"):
            PortfolioCapitalConsumptionService.evaluate(
                (exposure("C1", "Coocique", "CRC", value, ExposureClass.UNRATED),)
            )
