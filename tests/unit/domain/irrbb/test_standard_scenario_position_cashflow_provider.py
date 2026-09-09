from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    IRRBBCashFlow,
    IRRBBInstrumentClass,
    IRRBBScenario,
    OptionalityType,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.services.standard_scenario_position_cashflow_provider import (
    StandardScenarioPositionCashFlowProvider,
)
from aip.shared.money import Currency, Money

_VALUATION_DATE = date(2026, 8, 31)
_CRC = Currency.CRC


class _Builder:
    def build(
        self,
        *,
        position: BankingBookPosition,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        del valuation_date
        status = (
            CashFlowAmountStatus.PROJECTED_CURRENT_RATE
            if position.rate_type is RateType.FLOATING
            else CashFlowAmountStatus.CONTRACTUAL
        )
        return (
            IRRBBCashFlow(
                position_id=position.position_id,
                side=position.side,
                direction=(
                    CashFlowDirection.RECEIVABLE
                    if position.side is BankingBookSide.ASSET
                    else CashFlowDirection.PAYABLE
                ),
                amount=Money(Decimal("100"), position.currency),
                cashflow_date=date(2027, 8, 31),
                risk_date=date(2026, 11, 30),
                flow_type="INTEREST",
                source_reference=f"TEST:{position.position_id}:BASE",
                amount_status=status,
            ),
        )


class _Resolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, *, position: BankingBookPosition) -> _Builder:
        del position
        self.calls += 1
        return _Builder()


class _Projector:
    def __init__(self) -> None:
        self.calls = 0

    def project(
        self,
        *,
        position: BankingBookPosition,
        base_cashflows: tuple[IRRBBCashFlow, ...],
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        del valuation_date
        self.calls += 1
        base = base_cashflows[0]
        return (
            IRRBBCashFlow(
                position_id=position.position_id,
                side=base.side,
                direction=base.direction,
                amount=Money(Decimal("120"), base.amount.currency),
                cashflow_date=base.cashflow_date,
                risk_date=base.risk_date,
                flow_type=base.flow_type,
                source_reference=base.source_reference,
                amount_status=CashFlowAmountStatus.SCENARIO_PROJECTED,
                projection_basis=f"TEST:{scenario.value}",
            ),
        )


class _NMDModel:
    def __init__(self) -> None:
        self.calls = 0

    def apply(
        self,
        *,
        position: BankingBookPosition,
        contractual_cashflows: tuple[IRRBBCashFlow, ...],
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> tuple[IRRBBCashFlow, ...]:
        assert contractual_cashflows == ()
        self.calls += 1
        return (
            IRRBBCashFlow(
                position_id=position.position_id,
                side=position.side,
                direction=CashFlowDirection.PAYABLE,
                amount=Money(position.principal.amount, position.currency),
                cashflow_date=valuation_date,
                risk_date=valuation_date,
                flow_type="BEHAVIORAL_PRINCIPAL",
                source_reference=position.source_reference,
                amount_status=CashFlowAmountStatus.BEHAVIORAL,
                projection_basis=f"TEST:{scenario.value}",
            ),
        )


def _position(
    *,
    position_id: str,
    rate_type: RateType,
    instrument_class: IRRBBInstrumentClass = IRRBBInstrumentClass.CREDIT,
    optionality: OptionalityType = OptionalityType.NONE,
    payment_structure: PaymentStructure = PaymentStructure.BULLET,
    side: BankingBookSide = BankingBookSide.ASSET,
) -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type="TEST",
        side=side,
        currency=_CRC,
        principal=Money(Decimal("1000"), _CRC),
        rate_type=rate_type,
        maturity_date=(
            None
            if instrument_class is IRRBBInstrumentClass.NON_MATURITY_DEPOSIT
            else date(2028, 8, 31)
        ),
        source_reference=f"TEST:{position_id}",
        next_repricing_date=(date(2026, 11, 30) if rate_type is RateType.FLOATING else None),
        repricing_frequency_months=(3 if rate_type is RateType.FLOATING else None),
        instrument_class=instrument_class,
        optionality=optionality,
        payment_structure=payment_structure,
    )


def test_fixed_rate_stress_uses_contractual_schedule_without_projector() -> None:
    resolver = _Resolver()
    projector = _Projector()
    provider = StandardScenarioPositionCashFlowProvider(
        builder_resolver=resolver,
        scenario_projector=projector,
    )

    result = provider.cashflows_for(
        position=_position(position_id="FIXED", rate_type=RateType.FIXED),
        scenario=IRRBBScenario.PARALLEL_UP,
        valuation_date=_VALUATION_DATE,
    )

    assert result[0].amount_status is CashFlowAmountStatus.CONTRACTUAL
    assert resolver.calls == 1
    assert projector.calls == 0


def test_floating_rate_stress_uses_scenario_projector() -> None:
    resolver = _Resolver()
    projector = _Projector()
    provider = StandardScenarioPositionCashFlowProvider(
        builder_resolver=resolver,
        scenario_projector=projector,
    )

    result = provider.cashflows_for(
        position=_position(position_id="FLOAT", rate_type=RateType.FLOATING),
        scenario=IRRBBScenario.PARALLEL_UP,
        valuation_date=_VALUATION_DATE,
    )

    assert result[0].amount == Money(Decimal("120"), _CRC)
    assert result[0].amount_status is CashFlowAmountStatus.SCENARIO_PROJECTED
    assert projector.calls == 1


def test_floating_rate_base_does_not_require_scenario_projector() -> None:
    provider = StandardScenarioPositionCashFlowProvider(builder_resolver=_Resolver())

    result = provider.cashflows_for(
        position=_position(position_id="FLOAT-BASE", rate_type=RateType.FLOATING),
        scenario=IRRBBScenario.BASE,
        valuation_date=_VALUATION_DATE,
    )

    assert result[0].amount_status is CashFlowAmountStatus.PROJECTED_CURRENT_RATE


def test_floating_rate_stress_without_projector_is_rejected() -> None:
    provider = StandardScenarioPositionCashFlowProvider(builder_resolver=_Resolver())

    with pytest.raises(ValueError, match="requires a scenario cash-flow projector"):
        provider.cashflows_for(
            position=_position(position_id="FLOAT-NO-PROJECTOR", rate_type=RateType.FLOATING),
            scenario=IRRBBScenario.PARALLEL_UP,
            valuation_date=_VALUATION_DATE,
        )


def test_nmd_uses_behavioral_model_without_contractual_builder() -> None:
    resolver = _Resolver()
    nmd_model = _NMDModel()
    provider = StandardScenarioPositionCashFlowProvider(
        builder_resolver=resolver,
        nmd_behavioral_model=nmd_model,
    )
    position = _position(
        position_id="NMD",
        rate_type=RateType.FLOATING,
        instrument_class=IRRBBInstrumentClass.NON_MATURITY_DEPOSIT,
        optionality=OptionalityType.NON_MATURITY_DEPOSIT,
        payment_structure=PaymentStructure.NON_MATURITY,
        side=BankingBookSide.LIABILITY,
    )

    result = provider.cashflows_for(
        position=position,
        scenario=IRRBBScenario.PARALLEL_DOWN,
        valuation_date=_VALUATION_DATE,
    )

    assert result[0].amount_status is CashFlowAmountStatus.BEHAVIORAL
    assert resolver.calls == 0
    assert nmd_model.calls == 1


def test_material_prepayment_optionality_is_blocked_until_integrated_strategy_exists() -> None:
    provider = StandardScenarioPositionCashFlowProvider(builder_resolver=_Resolver())
    position = _position(
        position_id="PREPAY",
        rate_type=RateType.FIXED,
        optionality=OptionalityType.LOAN_PREPAYMENT,
    )

    with pytest.raises(ValueError, match="integrated scenario-specific behavioral strategy"):
        provider.cashflows_for(
            position=position,
            scenario=IRRBBScenario.PARALLEL_UP,
            valuation_date=_VALUATION_DATE,
        )
