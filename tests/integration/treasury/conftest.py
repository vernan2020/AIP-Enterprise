from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.shared.conventions import DayCountConvention
from src.extensions.coopealianza.liquidity.mil.configuration.mil_policy_config import (
    MilHaircutConfig,
    MilPolicyConfig,
)
from src.extensions.coopealianza.liquidity.mil.models.mil_asset import MilAsset
from src.extensions.coopealianza.liquidity.stress.configuration.stress_policy_config import (
    StressPolicyConfig,
    StressScenarioConfig,
)


class TreasuryInstrument(GovernmentBond):
    def __init__(self) -> None:
        issuer = Issuer(code="coope", name="Coopealianza", issuer_type=IssuerType.GOVERNMENT)
        super().__init__(
            isin="COOP123",
            name="Treasury Bond",
            issuer=issuer,
            currency="USD",
            settlement_calendar="USD",
            business_day_convention="FOLLOWING",
            day_count_convention=DayCountConvention.ACTUAL_365,
            issue_date=date(2020, 1, 1),
            settlement_date=date(2020, 1, 3),
            maturity_date=date(2030, 1, 1),
            coupon_schedule=None,
            nominal_value=Decimal("1000000"),
            book_value=Decimal("1000000"),
            market_value=Decimal("1000000"),
            face_value=Decimal("1000000"),
            outstanding_amount=Decimal("1000000"),
            yield_rate=Decimal("0.03"),
            duration=Decimal("4"),
            modified_duration=Decimal("4"),
            convexity=Decimal("0.5"),
            dirty_price=Decimal("1000000"),
            clean_price=Decimal("1000000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.05"),
            payment_frequency=PaymentFrequency.SEMIANNUAL,
        )


@pytest.fixture
def treasury_instrument() -> TreasuryInstrument:
    return TreasuryInstrument()


@pytest.fixture
def yield_curve() -> YieldCurve:
    return YieldCurve(
        valuation_date=date(2026, 1, 1),
        currency="USD",
        points=(
            CurvePoint(tenor=Decimal("1"), zero_rate=Decimal("0.03")),
            CurvePoint(tenor=Decimal("10"), zero_rate=Decimal("0.04")),
        ),
    )


@pytest.fixture
def analysis_request(
    treasury_instrument: TreasuryInstrument, yield_curve: YieldCurve
) -> AnalysisRequest:
    return AnalysisRequest(
        workflow_id="wf-treasury",
        correlation_id="corr-treasury",
        valuation_date=date(2026, 1, 1),
        instrument=treasury_instrument,
        market_yield=Decimal("0.04"),
        curve=yield_curve,
        market_price=Decimal("1000000"),
        benchmark_yield=Decimal("0.05"),
        context={
            "deterministic_ids": True,
            "contractual_cashflows": (
                CashFlow(
                    payment_date=date(2026, 6, 1),
                    amount=Decimal("500000"),
                    currency="USD",
                    cash_flow_type="coupon",
                ),
                CashFlow(
                    payment_date=date(2027, 6, 1),
                    amount=Decimal("300000"),
                    currency="USD",
                    cash_flow_type="principal",
                ),
            ),
        },
        requested_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def projection_request() -> ProjectionRequest:
    return ProjectionRequest(
        valuation_date=date(2026, 1, 1),
        contractual_cashflows=(
            CashFlow(
                payment_date=date(2026, 6, 1),
                amount=Decimal("500000"),
                currency="USD",
                cash_flow_type="coupon",
            ),
            CashFlow(
                payment_date=date(2027, 6, 1),
                amount=Decimal("300000"),
                currency="USD",
                cash_flow_type="principal",
            ),
        ),
        portfolio_reference="portfolio-1",
        currency="USD",
        projection_type="contractual",
    )


@pytest.fixture
def mil_asset() -> MilAsset:
    return MilAsset(
        position_id="pos-1",
        instrument_id="bond-1",
        isin="COOP123",
        issuer="Coopealianza",
        issuer_category="cooperative",
        currency="USD",
        nominal_amount=Decimal("1000000"),
        market_value=Decimal("1000000"),
        accounting_value=Decimal("1000000"),
        classification="government",
        encumbrance_status="unencumbered",
        reserve_liquidity_status="normal",
        operational_availability=True,
        settlement_capability="delivery_vs_payment",
        valuation_date=date(2026, 1, 1),
        market_price_date=date(2026, 1, 1),
        maturity_date=date(2030, 1, 1),
        portfolio_reference="portfolio-1",
    )


@pytest.fixture
def mil_config() -> MilPolicyConfig:
    return MilPolicyConfig(
        policy_id="mil-policy",
        version="1.0",
        name="MIL Policy",
        category="mil",
        eligible_issuer_categories=("cooperative", "government"),
        acceptable_settlement_rules=("delivery_vs_payment",),
        haircut_mappings=(
            MilHaircutConfig(issuer_category="cooperative", haircut=Decimal("0.05")),
        ),
        policy_references=(PolicyReference(source="coopealianza", identifier="MIL-REF"),),
    )


@pytest.fixture
def stress_config() -> StressPolicyConfig:
    return StressPolicyConfig(
        policy_id="stress-policy",
        version="1.0",
        name="Stress Policy",
        category="stress",
        scenarios=(
            StressScenarioConfig(
                scenario_id="s1",
                name="parallel_shift",
                scenario_type="parallel_shift",
                severity=Decimal("0.10"),
                liquidity_factor=Decimal("0.05"),
                concentration_factor=Decimal("0.02"),
                policy_references=("STRESS-REF",),
                affected_assets=("bond-1",),
                affected_buckets=("O/N",),
                assumptions=("stable liquidity",),
                warnings=("watch",),
            ),
        ),
    )
