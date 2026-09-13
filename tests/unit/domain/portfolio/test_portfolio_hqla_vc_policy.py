from decimal import Decimal

from aip.domain.portfolio.services.portfolio_hqla_service import PortfolioHQLAService


def test_hqla_excludes_exact_vc_classification() -> None:
    result = PortfolioHQLAService.calculate(
        {
            "issuer": "G",
            "classification": "V.C",
            "market_value_crc": Decimal("100000000"),
        }
    )

    assert result.eligible is False
    assert result.factor == Decimal("0")
    assert result.hqla_value_crc == Decimal("0")
    assert result.status == "RESTRICTED"
    assert result.source == "CLASSIFICATION"


def test_hqla_excludes_any_classification_starting_with_vc() -> None:
    result = PortfolioHQLAService.calculate(
        {
            "issuer": "G",
            "classification": "V.C GOBIERNO",
            "market_value_crc": Decimal("100000000"),
        }
    )

    assert result.eligible is False
    assert result.status == "RESTRICTED"
    assert result.hqla_value_crc == Decimal("0")


def test_hqla_vr_bccr_remains_eligible() -> None:
    result = PortfolioHQLAService.calculate(
        {
            "issuer": "BCCR",
            "classification": "V.R BCCR",
            "market_value_crc": Decimal("100000000"),
        }
    )

    assert result.eligible is True
    assert result.factor == Decimal("0.90")
    assert result.hqla_value_crc == Decimal("90000000.00")
    assert result.status == "HQLA_90"
    assert result.source == "BCCR"
