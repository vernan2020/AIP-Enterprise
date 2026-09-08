from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_hqla_service import PortfolioHQLAService
from aip.domain.portfolio.services.portfolio_mil_service import PortfolioMILService


def test_hqla_rejects_missing_or_zero_market_value() -> None:
    result = PortfolioHQLAService.calculate(
        {
            "issuer": "G",
            "classification": "D.V GOBIERNO",
            "market_value_crc": Decimal("0"),
        }
    )

    assert result.eligible is False
    assert result.factor == Decimal("0")
    assert result.hqla_value_crc == Decimal("0")
    assert result.status == "NOT_ELIGIBLE"
    assert result.source == "MARKET_VALUE"


def test_hqla_restricted_reserva_de_liquidez_is_excluded() -> None:
    result = PortfolioHQLAService.calculate(
        {
            "issuer": "G",
            "classification": "D.V-RL GOBIERNO",
            "market_value_crc": Decimal("100000000"),
        }
    )

    assert result.eligible is False
    assert result.status == "RESTRICTED"
    assert result.source == "CLASSIFICATION"
    assert result.hqla_value_crc == Decimal("0")


def test_hqla_bccr_icp_receives_one_hundred_percent_factor() -> None:
    result = PortfolioHQLAService.calculate(
        {
            "issuer": "BCCR",
            "product_code": "ICP",
            "classification": "V.R BCCR",
            "market_value_crc": Decimal("125000000"),
        }
    )

    assert result.eligible is True
    assert result.factor == Decimal("1")
    assert result.hqla_value_crc == Decimal("125000000")
    assert result.status == "HQLA_100"
    assert result.source == "BCCR_ICP"


def test_hqla_government_available_security_receives_ninety_percent_factor() -> None:
    result = PortfolioHQLAService.calculate(
        {
            "issuer": "G",
            "classification": "D.V GOBIERNO",
            "market_value_crc": Decimal("100000000"),
        }
    )

    assert result.eligible is True
    assert result.factor == Decimal("0.90")
    assert result.hqla_value_crc == Decimal("90000000.00")
    assert result.status == "HQLA_90"
    assert result.source == "GOVERNMENT"


def test_hqla_bccr_available_security_receives_ninety_percent_factor() -> None:
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known characterization gap: PortfolioHQLAService does not yet exclude every "
        "classification whose institutional code starts with V.C. This test records the "
        "required policy gate without changing methodology in the characterization PR."
    ),
)
def test_hqla_vc_classification_is_restricted_by_institutional_policy() -> None:
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


def test_mil_rejects_missing_or_zero_market_value() -> None:
    result = PortfolioMILService.calculate(
        {
            "issuer": "G",
            "classification": "D.V GOBIERNO",
            "market_value_crc": None,
        }
    )

    assert result.eligible is False
    assert result.factor == Decimal("0")
    assert result.mil_value_crc == Decimal("0")
    assert result.status == "NOT_ELIGIBLE"
    assert result.source == "MARKET_VALUE"


def test_mil_restricted_reserva_de_liquidez_is_excluded() -> None:
    result = PortfolioMILService.calculate(
        {
            "issuer": "G",
            "classification": "Reserva de Liquidez - Gobierno",
            "market_value_crc": Decimal("100000000"),
        }
    )

    assert result.eligible is False
    assert result.status == "RESTRICTED"
    assert result.source == "CLASSIFICATION"
    assert result.mil_value_crc == Decimal("0")


def test_mil_government_available_security_receives_ninety_percent_factor() -> None:
    result = PortfolioMILService.calculate(
        {
            "issuer": "G",
            "classification": "D.V GOBIERNO",
            "market_value_crc": Decimal("200000000"),
        }
    )

    assert result.eligible is True
    assert result.factor == Decimal("0.90")
    assert result.mil_value_crc == Decimal("180000000.00")
    assert result.status == "MIL_ELIGIBLE"
    assert result.source == "GOVERNMENT_COLLATERAL"


def test_mil_bccr_available_security_receives_ninety_percent_factor() -> None:
    result = PortfolioMILService.calculate(
        {
            "issuer": "BCCR",
            "classification": "V.R BCCR",
            "product_code": "BONO",
            "market_value_crc": Decimal("100000000"),
        }
    )

    assert result.eligible is True
    assert result.factor == Decimal("0.90")
    assert result.mil_value_crc == Decimal("90000000.00")
    assert result.status == "MIL_ELIGIBLE"
    assert result.source == "BCCR_COLLATERAL"


def test_mil_bccr_icp_is_not_eligible_collateral() -> None:
    result = PortfolioMILService.calculate(
        {
            "issuer": "BCCR",
            "classification": "V.R BCCR",
            "product_code": "ICP",
            "market_value_crc": Decimal("100000000"),
        }
    )

    assert result.eligible is False
    assert result.factor == Decimal("0")
    assert result.mil_value_crc == Decimal("0")
    assert result.status == "NOT_ELIGIBLE"
    assert result.source == "BCCR_ICP"
