from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.gap.engine.gap_engine import GapEngine
from aip.domain.liquidity.gap.exceptions import CurrencyMismatchError, GapProviderError
from aip.domain.liquidity.gap.models.gap_request import GapRequest
from aip.domain.liquidity.gap.providers.gap_provider import GapProvider


class _StaticGapProvider(GapProvider):
    def get_projection_request(self, request: GapRequest) -> ProjectionRequest:
        return ProjectionRequest(
            valuation_date=request.valuation_date,
            contractual_cashflows=(
                CashFlow(
                    payment_date=date(2024, 2, 1),
                    amount=Decimal("100"),
                    currency="USD",
                    cash_flow_type="coupon",
                ),
                CashFlow(
                    payment_date=date(2024, 3, 1),
                    amount=Decimal("-40"),
                    currency="USD",
                    cash_flow_type="principal",
                ),
            ),
            business_unit="treasury",
            portfolio_reference="pf-1",
            product_type="loan",
            counterparty="cpty-a",
            instrument_id="inst-1",
            currency="USD",
        )


class _BrokenGapProvider(GapProvider):
    def get_projection_request(self, request: GapRequest) -> ProjectionRequest:
        raise RuntimeError("boom")


def test_gap_engine_builds_net_gross_incremental_and_cumulative_values() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(
                CashFlow(
                    payment_date=date(2024, 2, 1),
                    amount=Decimal("100"),
                    currency="USD",
                    cash_flow_type="coupon",
                ),
                CashFlow(
                    payment_date=date(2024, 3, 1),
                    amount=Decimal("-40"),
                    currency="USD",
                    cash_flow_type="principal",
                ),
            ),
        ),
    )

    result = GapEngine().project(request)

    assert result.gap_type == "net"
    assert result.net_gap == Decimal("60")
    assert result.gross_inflow == Decimal("100")
    assert result.gross_outflow == Decimal("40")
    assert result.incremental_gap == Decimal("60")
    assert result.cumulative_gap == Decimal("60")
    assert result.summary_value == Decimal("60")
    assert result.gaps[0].net_gap == Decimal("100")
    assert result.gaps[1].net_gap == Decimal("-40")


def test_gap_engine_supports_contractual_behavioral_and_scenario_summary_values() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(
                CashFlow(
                    payment_date=date(2024, 2, 1),
                    amount=Decimal("100"),
                    currency="USD",
                    cash_flow_type="coupon",
                ),
            ),
        ),
        gap_type="behavioral",
    )

    result = GapEngine().project(request)

    assert result.gap_type == "behavioral"
    assert result.summary_value == Decimal("0")


def test_gap_engine_aggregates_deterministically_across_dimensions() -> None:
    GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(
                CashFlow(
                    payment_date=date(2024, 2, 1),
                    amount=Decimal("100"),
                    currency="USD",
                    cash_flow_type="coupon",
                ),
                CashFlow(
                    payment_date=date(2024, 3, 1),
                    amount=Decimal("50"),
                    currency="EUR",
                    cash_flow_type="principal",
                ),
            ),
            business_unit="treasury",
            portfolio_reference="pf-1",
            product_type="loan",
            counterparty="cpty-a",
            instrument_id="inst-1",
        ),
    )

    result = GapEngine().project(
        GapRequest(
            valuation_date=date(2024, 1, 1),
            cashflow_request=ProjectionRequest(
                valuation_date=date(2024, 1, 1),
                contractual_cashflows=(
                    CashFlow(
                        payment_date=date(2024, 2, 1),
                        amount=Decimal("100"),
                        currency="USD",
                        cash_flow_type="coupon",
                    ),
                    CashFlow(
                        payment_date=date(2024, 3, 1),
                        amount=Decimal("50"),
                        currency="EUR",
                        cash_flow_type="principal",
                    ),
                ),
                business_unit="treasury",
                portfolio_reference="pf-1",
                product_type="loan",
                counterparty="cpty-a",
                instrument_id="inst-1",
            ),
            exchange_rate_policy_provider=type(
                "Rate",
                (),
                {
                    "get_rate": lambda self, from_currency, to_currency, valuation_date=None: Decimal(
                        "1"
                    )
                },
            )(),
        )
    )

    assert result.aggregation["bucket"]["treasury"] == Decimal("150")
    assert result.aggregation["currency"]["USD"] == Decimal("100")
    assert result.aggregation["currency"]["EUR"] == Decimal("50")
    assert result.aggregation["product"]["loan"] == Decimal("150")
    assert result.aggregation["counterparty"]["cpty-a"] == Decimal("150")
    assert result.aggregation["instrument"]["inst-1"] == Decimal("150")
    assert result.aggregation["portfolio"]["pf-1"] == Decimal("150")
    assert result.aggregation["business_unit"]["treasury"] == Decimal("150")


def test_gap_engine_rejects_currency_mismatch() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        cashflow_request=ProjectionRequest(
            valuation_date=date(2024, 1, 1),
            contractual_cashflows=(
                CashFlow(
                    payment_date=date(2024, 2, 1),
                    amount=Decimal("100"),
                    currency="USD",
                    cash_flow_type="coupon",
                ),
            ),
            currency="USD",
        ),
        currency="EUR",
    )

    with pytest.raises(CurrencyMismatchError):
        GapEngine().project(request)


def test_gap_engine_translates_provider_failures_to_domain_exceptions() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        gap_provider=_BrokenGapProvider(),
    )

    with pytest.raises(GapProviderError):
        GapEngine().project(request)


def test_gap_engine_uses_provider_supplied_projection_request() -> None:
    request = GapRequest(
        valuation_date=date(2024, 1, 1),
        gap_provider=_StaticGapProvider(),
    )

    result = GapEngine().project(request)

    assert result.net_gap == Decimal("60")
    assert result.aggregation["business_unit"]["treasury"] == Decimal("60")
