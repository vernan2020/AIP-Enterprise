from decimal import Decimal

import pytest

from aip.domain.portfolio.services.capital_equivalent_rate_service import (
    CapitalEquivalentRateInput,
    CapitalEquivalentRateService,
)
from aip.domain.portfolio.services.portfolio_capital_consumption_service import ExposureClass


def calculate(exposure_class: ExposureClass):
    return CapitalEquivalentRateService.calculate(
        CapitalEquivalentRateInput(
            invested_amount_crc=Decimal("100000000"),
            regulatory_exposure_crc=Decimal("100000000"),
            annual_net_yield=Decimal("0.08"),
            exposure_class=exposure_class,
            annual_cost_of_equity=Decimal("0.12"),
        )
    )


def test_category_four_75pct_weight_under_16pct_capital_target() -> None:
    result = calculate(ExposureClass.RATED_4)
    assert result.risk_weight == Decimal("0.75")
    assert result.required_capital_crc == Decimal("12000000.0000")
    assert result.annual_equity_charge_crc == Decimal("1440000.000000")
    assert result.annual_equity_charge_rate == Decimal("0.0144")
    assert result.equivalent_yield_at_reference_risk_weight == Decimal("0.0656")


def test_unrated_coocique_100pct_weight_versus_category_four() -> None:
    unrated = calculate(ExposureClass.UNRATED)
    category_four = calculate(ExposureClass.RATED_4)
    assert unrated.risk_weight == Decimal("1")
    assert unrated.required_capital_crc == Decimal("16000000.00")
    assert unrated.equivalent_yield_at_reference_risk_weight == Decimal("0.0608")
    assert category_four.equivalent_yield_at_reference_risk_weight > unrated.equivalent_yield_at_reference_risk_weight


def test_sovereign_crc_has_no_credit_equity_charge() -> None:
    result = calculate(ExposureClass.BCCR_CRC)
    assert result.required_capital_crc == 0
    assert result.equivalent_yield_at_reference_risk_weight == Decimal("0.08")


def test_missing_equity_hurdle_is_not_assumed_from_16pct_target() -> None:
    with pytest.raises(TypeError):
        CapitalEquivalentRateInput(
            invested_amount_crc=Decimal("100"),
            regulatory_exposure_crc=Decimal("100"),
            annual_net_yield=Decimal("0.08"),
            exposure_class=ExposureClass.RATED_4,
        )


def test_exposure_basis_may_differ_from_investment_amount() -> None:
    result = CapitalEquivalentRateService.calculate(
        CapitalEquivalentRateInput(
            invested_amount_crc=Decimal("200"),
            regulatory_exposure_crc=Decimal("100"),
            annual_net_yield=Decimal("0.08"),
            exposure_class=ExposureClass.RATED_4,
            annual_cost_of_equity=Decimal("0.12"),
        )
    )
    assert result.annual_equity_charge_rate == Decimal("0.0072")


def test_usd_sovereigns_use_75pct_in_equivalent_yield() -> None:
    for classification in (ExposureClass.GOVERNMENT_USD, ExposureClass.BCCR_USD):
        result = calculate(classification)
        assert result.risk_weight == Decimal("0.75")
        assert result.required_capital_crc == Decimal("12000000.0000")
        assert result.equivalent_yield_at_reference_risk_weight == Decimal("0.0656")
