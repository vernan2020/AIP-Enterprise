from __future__ import annotations

from datetime import date

from aip.product.configured.adapters.configured_contractual_liquidity_provider import (
    ConfiguredContractualLiquidityProvider,
)
from aip.product.demo.configuration.demo_config import DemoConfig


def test_liquidity_uses_nominal_principal_and_includes_coupon_inflows() -> None:
    provider = ConfiguredContractualLiquidityProvider(
        DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    )
    result: dict[str, object] = {}
    positions = [
        {
            "series": "TEST-USD",
            "issuer": "TEST",
            "currency": "USD",
            "classification": "TEST",
            "nominal": 1000.0,
            "nominal_rate": 12.0,
            "periodicity": "trimestral",
            "last_interest_payment_date": date(2026, 1, 15),
            "maturity_date": date(2026, 4, 15),
            "variable_rate_flag": "N",
            "market_value_local": 900.0,
            "market_value": 900.0,
            "market_value_crc": 450_000.0,
            "hqla_status": "NOT_ELIGIBLE",
            "mil_status": "NOT_ELIGIBLE",
        }
    ]

    provider._populate_portfolio_liquidity(
        result=result,
        positions=positions,
        valuation_date=date(2026, 1, 15),
    )

    assert result["principal_inflows_90d_crc"] == 500_000.0
    assert result["coupon_inflows_90d_crc"] == 15_000.0
    assert result["investment_inflows_90d_crc"] == 515_000.0
    assert result["maturity_90d_crc"] == 500_000.0

    maturity_rows = result["maturity_rows"]
    assert isinstance(maturity_rows, list)
    assert maturity_rows[0]["value"] == 500_000.0
    assert maturity_rows[0]["market_value_crc"] == 450_000.0

    cashflows = result["cashflows"]
    assert isinstance(cashflows, list)
    assert {row["flow_type"] for row in cashflows} == {"COUPON", "PRINCIPAL"}
    assert all(row["conversion_source"] == "MARKET_VALUE_IMPLIED_FX" for row in cashflows)


def test_liquidity_does_not_invent_crc_conversion_when_fx_is_unavailable() -> None:
    provider = ConfiguredContractualLiquidityProvider(
        DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    )
    result: dict[str, object] = {}
    positions = [
        {
            "series": "TEST-USD-NOFX",
            "issuer": "TEST",
            "currency": "USD",
            "nominal": 1000.0,
            "nominal_rate": 0.0,
            "periodicity": "No aplica",
            "maturity_date": date(2026, 2, 15),
            "market_value_local": 0.0,
            "market_value_crc": 0.0,
            "hqla_status": "NOT_ELIGIBLE",
            "mil_status": "NOT_ELIGIBLE",
        }
    ]

    provider._populate_portfolio_liquidity(
        result=result,
        positions=positions,
        valuation_date=date(2026, 1, 15),
    )

    assert result["principal_inflows_90d_crc"] == 0.0
    assert result["cashflow_conversion_unavailable_count"] == 1
    cashflows = result["cashflows"]
    assert isinstance(cashflows, list)
    assert cashflows[0]["status"] == "FX_UNAVAILABLE"
