from datetime import date
from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_dv01_bucket_service import PortfolioDV01BucketService
from aip.domain.portfolio.services.portfolio_dv01_service import PortfolioDV01Service
from aip.domain.portfolio.services.portfolio_rate_shock_service import PortfolioRateShockService
from aip.domain.portfolio.services.portfolio_security_identity_service import (
    PortfolioSecurityIdentityService,
)


def test_dv01_uses_modified_duration_approximation() -> None:
    result = PortfolioDV01Service.calculate(
        {
            "market_value_crc": Decimal("100000000"),
            "modified_duration": Decimal("2"),
            "product_code": "BONO",
        }
    )

    assert result.status == "CALCULATED"
    assert result.method == "MODIFIED_DURATION_APPROXIMATION"
    assert result.source == "PORTFOLIO_DURATION_SERVICE"
    assert result.dv01_crc == Decimal("20000.0000")
    assert result.market_value_crc == Decimal("100000000")
    assert result.modified_duration == Decimal("2")


def test_dv01_zero_market_value_is_data_unavailable() -> None:
    result = PortfolioDV01Service.calculate(
        {
            "market_value_crc": Decimal("0"),
            "modified_duration": Decimal("2"),
            "product_code": "BONO",
        }
    )

    assert result.status == "DATA_UNAVAILABLE"
    assert result.method == "UNAVAILABLE"
    assert result.source == "MARKET_VALUE_CRC"
    assert result.dv01_crc is None


@pytest.mark.parametrize("product_code", ["FIPRC", "FINPO", "ILM1$", "INM1$", "INM2$", "INM3", "INSM$"])
def test_dv01_policy_excludes_products_without_duration(product_code: str) -> None:
    result = PortfolioDV01Service.calculate(
        {
            "market_value_crc": Decimal("100000000"),
            "modified_duration": Decimal("2"),
            "product_code": product_code,
        }
    )

    assert result.status == "POLICY_EXCLUDED"
    assert result.method == "NOT_APPLICABLE"
    assert result.source == "INSTITUTIONAL_DV01_POLICY"
    assert result.exclusion_reason == "INSTRUMENT_WITHOUT_DURATION"
    assert result.dv01_crc is None
    assert result.modified_duration is None


def test_dv01_negative_duration_is_data_unavailable() -> None:
    result = PortfolioDV01Service.calculate(
        {
            "market_value_crc": Decimal("100000000"),
            "modified_duration": Decimal("-1"),
            "product_code": "BONO",
        }
    )

    assert result.status == "DATA_UNAVAILABLE"
    assert result.source == "PORTFOLIO_DURATION_SERVICE"
    assert result.dv01_crc is None
    assert result.modified_duration == Decimal("-1")


def test_dv01_bucket_fixed_rate_uses_contractual_maturity() -> None:
    valuation_date = date(2026, 8, 28)

    assert (
        PortfolioDV01BucketService.bucket_key(
            {"variable_rate_flag": "N", "maturity_date": date(2027, 8, 27)},
            valuation_date=valuation_date,
        )
        == "< 1 año"
    )
    assert (
        PortfolioDV01BucketService.bucket_key(
            {"variable_rate_flag": "N", "maturity_date": date(2027, 8, 28)},
            valuation_date=valuation_date,
        )
        == "1 a 5 años"
    )
    assert (
        PortfolioDV01BucketService.bucket_key(
            {"variable_rate_flag": "N", "maturity_date": date(2031, 8, 28)},
            valuation_date=valuation_date,
        )
        == "1 a 5 años"
    )
    assert (
        PortfolioDV01BucketService.bucket_key(
            {"variable_rate_flag": "N", "maturity_date": date(2031, 8, 29)},
            valuation_date=valuation_date,
        )
        == "> 5 años"
    )


def test_dv01_bucket_variable_rate_uses_next_repricing_date() -> None:
    result = PortfolioDV01BucketService.bucket_key(
        {
            "variable_rate_flag": "S",
            "next_repricing_date": "2026-10-01",
            "maturity_date": "2036-01-01",
        },
        valuation_date=date(2026, 8, 28),
    )

    assert result == "< 1 año"


def test_dv01_bucket_returns_none_when_reference_date_is_unavailable() -> None:
    result = PortfolioDV01BucketService.bucket_key(
        {"variable_rate_flag": "N", "maturity_date": "not-a-date"},
        valuation_date=date(2026, 8, 28),
    )

    assert result is None


def test_rate_shock_positive_100bp_reduces_eve_under_duration_approximation() -> None:
    result = PortfolioRateShockService.calculate(
        {
            "market_value_crc": Decimal("100000000"),
            "modified_duration": Decimal("2"),
            "product_code": "BONO",
        },
        100,
    )

    assert result.status == "CALCULATED"
    assert result.method == "MODIFIED_DURATION_APPROXIMATION"
    assert result.delta_eve_crc == Decimal("-2000000.00")
    assert result.shocked_market_value_crc == Decimal("98000000.00")


def test_rate_shock_negative_100bp_increases_eve_under_duration_approximation() -> None:
    result = PortfolioRateShockService.calculate(
        {
            "market_value_crc": Decimal("100000000"),
            "modified_duration": Decimal("2"),
            "product_code": "BONO",
        },
        -100,
    )

    assert result.delta_eve_crc == Decimal("2000000.00")
    assert result.shocked_market_value_crc == Decimal("102000000.00")


def test_rate_shock_rejects_unsupported_parallel_shock() -> None:
    with pytest.raises(ValueError, match="Unsupported rate shock: 50 bp"):
        PortfolioRateShockService.calculate(
            {
                "market_value_crc": Decimal("100000000"),
                "modified_duration": Decimal("2"),
                "product_code": "BONO",
            },
            50,
        )


def test_rate_shock_excludes_product_without_duration() -> None:
    result = PortfolioRateShockService.calculate(
        {
            "market_value_crc": Decimal("100000000"),
            "modified_duration": Decimal("2"),
            "product_code": "FIPRC",
        },
        200,
    )

    assert result.status == "POLICY_EXCLUDED"
    assert result.method == "NOT_APPLICABLE"
    assert result.source == "INSTITUTIONAL_RATE_RISK_POLICY"
    assert result.delta_eve_crc is None
    assert result.shocked_market_value_crc is None


def test_security_identity_prefers_isin_over_fallback_fields() -> None:
    identity = PortfolioSecurityIdentityService.from_position(
        {
            "isin": " CRTEST000001 ",
            "series": "SERIE-A",
            "issuer": "G",
            "maturity_date": date(2030, 1, 1),
        }
    )

    assert identity == "isin:crtest000001"


def test_security_identity_falls_back_to_series_issuer_and_maturity() -> None:
    identity = PortfolioSecurityIdentityService.from_position(
        {
            "isin": "",
            "series": " SERIE-A ",
            "issuer": " G ",
            "maturity_date": "2030-01-01T00:00:00",
        }
    )

    assert identity == "series:serie-a|issuer:g|maturity:2030-01-01"


def test_security_identity_accepts_alternate_series_and_maturity_fields() -> None:
    identity = PortfolioSecurityIdentityService.from_position(
        {
            "series_or_security_code": "ALT-1",
            "issuer": "BCCR",
            "maturity_date_if_present": date(2031, 6, 30),
        }
    )

    assert identity == "series:alt-1|issuer:bccr|maturity:2031-06-30"


def test_security_identity_uses_empty_maturity_when_invalid() -> None:
    identity = PortfolioSecurityIdentityService.from_position(
        {
            "series": "SERIE-A",
            "issuer": "G",
            "maturity_date": "invalid",
        }
    )

    assert identity == "series:serie-a|issuer:g|maturity:"
