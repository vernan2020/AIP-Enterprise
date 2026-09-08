from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.portfolio.services.portfolio_contractual_cashflow_service import (
    PortfolioContractualCashFlowService,
)


def test_fixed_rate_security_generates_coupon_schedule_and_principal() -> None:
    position = {
        "currency": "CRC",
        "nominal": 1_000_000,
        "nominal_rate": 12.0,
        "periodicity": "trimestral",
        "last_interest_payment_date": date(2026, 1, 15),
        "maturity_date": date(2026, 7, 15),
        "variable_rate_flag": "N",
    }

    flows = PortfolioContractualCashFlowService.calculate(position, date(2026, 1, 15))

    assert [(item.payment_date, item.flow_type) for item in flows] == [
        (date(2026, 4, 15), "COUPON"),
        (date(2026, 7, 15), "COUPON"),
        (date(2026, 7, 15), "PRINCIPAL"),
    ]
    assert flows[0].amount_local == Decimal("30000.00")
    assert flows[0].amount_status == "CONTRACTUAL"
    assert flows[-1].amount_local == Decimal("1000000")


def test_variable_rate_coupon_amount_is_explicitly_projected_at_current_rate() -> None:
    position = {
        "currency": "USD",
        "nominal": 1000,
        "nominal_rate": 8.0,
        "periodicity": "trimestral",
        "last_interest_payment_date": date(2026, 1, 15),
        "maturity_date": date(2026, 4, 15),
        "variable_rate_flag": "S",
    }

    flows = PortfolioContractualCashFlowService.calculate(position, date(2026, 1, 15))

    coupon = next(item for item in flows if item.flow_type == "COUPON")
    assert coupon.amount_local == Decimal("20.00")
    assert coupon.amount_status == "PROJECTED_CURRENT_RATE"
    assert coupon.source == "CURRENT_RATE_PROJECTION_VARIABLE_SECURITY"


def test_security_without_coupon_periodicity_still_returns_contractual_principal() -> None:
    position = {
        "currency": "CRC",
        "nominal": 250_000,
        "nominal_rate": 0.0,
        "periodicity": "No aplica",
        "maturity_date": date(2026, 2, 15),
    }

    flows = PortfolioContractualCashFlowService.calculate(position, date(2026, 1, 15))

    assert len(flows) == 1
    assert flows[0].flow_type == "PRINCIPAL"
    assert flows[0].amount_local == Decimal("250000")
