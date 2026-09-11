from datetime import date
from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_duration_service import PortfolioDurationService
from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.demo.configuration.demo_config import DemoConfig


def _fixed_rate_position(**overrides: object) -> dict[str, object]:
    position: dict[str, object] = {
        "product_code": "BOND",
        "market_yield": Decimal("0.05872768334279588"),
        "portfolio_yield": Decimal("0.06"),
        "nominal_rate": Decimal("0.0731"),
        "nominal": Decimal("106154200"),
        "maturity_date": date(2036, 7, 23),
        "periodicity": "semestral",
        "variable_rate_flag": "N",
    }
    position.update(overrides)
    return position


def test_fixed_rate_duration_uses_cash_flows_through_contractual_maturity() -> None:
    result = PortfolioDurationService.calculate(
        _fixed_rate_position(),
        date(2026, 8, 28),
    )

    assert result.method == "MODIFIED_DURATION"
    assert result.source == "PIPCA_MARKET_YIELD"
    assert result.included_in_portfolio_duration is True
    assert float(result.modified_duration or 0) == pytest.approx(7.1167, abs=0.01)


def test_fixed_rate_duration_falls_back_to_master_tir_then_facial_rate() -> None:
    master_result = PortfolioDurationService.calculate(
        _fixed_rate_position(market_yield=Decimal("0")),
        date(2026, 8, 28),
    )
    facial_result = PortfolioDurationService.calculate(
        _fixed_rate_position(
            market_yield=None,
            portfolio_yield=None,
            yield_value=None,
        ),
        date(2026, 8, 28),
    )

    assert master_result.modified_duration is not None
    assert master_result.source == "MASTER_TIR"
    assert facial_result.modified_duration is not None
    assert facial_result.source == "FACIAL_RATE_FALLBACK"


def test_variable_coupon_duration_uses_next_coupon_date() -> None:
    result = PortfolioDurationService.calculate(
        {
            "product_code": "BOND",
            "periodicity": "trimestral",
            "variable_rate_flag": "S",
            "market_yield": Decimal("0.06"),
            "last_interest_payment_date": date(2026, 6, 30),
            "maturity_date": date(2030, 6, 30),
        },
        date(2026, 8, 27),
    )

    assert result.method == "NEXT_REPRICING"
    assert result.source == "NEXT_COUPON_DATE"
    assert result.next_repricing_date == date(2026, 9, 30)
    assert result.modified_duration == (Decimal("34") / Decimal("365")) / Decimal("1.015")


def test_variable_coupon_infers_schedule_from_maturity_when_last_payment_is_missing() -> None:
    result = PortfolioDurationService.calculate(
        {
            "product_code": "BOND",
            "periodicity": "trimestral",
            "variable_rate_flag": "S",
            "market_yield": Decimal("0.06"),
            "last_interest_payment_date": None,
            "maturity_date": date(2030, 6, 30),
        },
        date(2026, 8, 27),
    )

    assert result.method == "NEXT_REPRICING"
    assert result.next_repricing_date == date(2026, 9, 30)
    assert result.modified_duration == (Decimal("34") / Decimal("365")) / Decimal("1.015")


def test_liquidity_operations_do_not_reduce_consolidated_fixed_income_duration() -> None:
    result = PortfolioDurationService.calculate(
        {
            "product_code": "MIL",
            "periodicity": "No aplica",
            "variable_rate_flag": "N",
            "maturity_date": date(2026, 9, 30),
        },
        date(2026, 8, 27),
    )

    assert result.modified_duration is not None
    assert result.included_in_portfolio_duration is False
    assert result.exclusion_reason == "LIQUIDITY_OPERATION_OUTSIDE_FIXED_INCOME_DURATION"


def test_portfolio_duration_weights_only_included_fixed_income_titles() -> None:
    provider = ConfiguredPortfolioProvider(DemoConfig())
    duration = provider._weighted_average_duration(
        [
            {
                "modified_duration": Decimal("2"),
                "market_value_crc": Decimal("100"),
                "duration_included": True,
            },
            {
                "modified_duration": Decimal("0.10"),
                "market_value_crc": Decimal("900"),
                "duration_included": False,
            },
        ]
    )

    assert duration == Decimal("2")
