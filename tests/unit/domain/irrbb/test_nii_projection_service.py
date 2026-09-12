from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    RateType,
)
from aip.domain.irrbb.nii import (
    NIIAccrualType,
    NIIBalanceSheetAssumption,
    NIIInterestAccrual,
    NIIProjectionBasis,
    NIIShockTiming,
)
from aip.domain.irrbb.nii_projection import (
    NIIPositionProjection,
    NIIPositionProjectionStatus,
    NIIProjectionBatch,
)
from aip.domain.irrbb.services.nii_projection_service import NIIProjectionService
from aip.shared.money import Currency, Money


def _basis() -> NIIProjectionBasis:
    return NIIProjectionBasis(
        methodology=IRRBBMethodologyProfile(
            code="INTERNAL-NII",
            version="2026.09.10",
            status=IRRBBMethodologyStatus.INTERNAL,
            source_reference="policy:nii",
        ),
        valuation_date=date(2026, 9, 10),
        horizon_end_date=date(2027, 9, 10),
        balance_sheet_assumption=NIIBalanceSheetAssumption.CONSTANT,
        shock_timing=NIIShockTiming.INSTANTANEOUS,
        source_reference="projection:approved-input",
    )


def _position(position_id: str) -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type="TEST",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2027, 6, 30),
        source_reference=f"source:{position_id}",
        contractual_rate=Decimal("0.05"),
    )


def _accrual(*, position_id: str, scenario: IRRBBScenario, accrual_id: str) -> NIIInterestAccrual:
    return NIIInterestAccrual(
        accrual_id=accrual_id,
        position_id=position_id,
        scenario=scenario,
        accrual_type=NIIAccrualType.INTEREST_INCOME,
        amount=Money(Decimal("10"), Currency.CRC),
        accrual_start_date=date(2026, 9, 10),
        accrual_end_date=date(2026, 10, 10),
        source_reference=f"source:{accrual_id}",
    )


class _Strategy:
    def __init__(self, *, projection_factory) -> None:  # type: ignore[no-untyped-def]
        self._projection_factory = projection_factory

    def project(
        self,
        *,
        position: BankingBookPosition,
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
    ) -> NIIPositionProjection:
        return self._projection_factory(position, basis, scenario)


class _Resolver:
    def __init__(self, strategy: _Strategy) -> None:
        self._strategy = strategy
        self.calls: list[str] = []

    def resolve(self, *, position: BankingBookPosition) -> _Strategy:
        self.calls.append(position.position_id)
        return self._strategy


def _projected(
    position: BankingBookPosition,
    basis: NIIProjectionBasis,
    scenario: IRRBBScenario,
) -> NIIPositionProjection:
    return NIIPositionProjection(
        position_id=position.position_id,
        scenario=scenario,
        basis=basis,
        strategy_reference="strategy:test-fixed",
        status=NIIPositionProjectionStatus.PROJECTED,
        accruals=(
            _accrual(
                position_id=position.position_id,
                scenario=scenario,
                accrual_id=f"{position.position_id}:{scenario.value}:1",
            ),
        ),
    )


def test_projection_service_preserves_one_result_per_position_and_flattens_accruals() -> None:
    positions = (_position("p1"), _position("p2"))
    resolver = _Resolver(_Strategy(projection_factory=_projected))

    result = NIIProjectionService.project(
        positions=positions,
        basis=_basis(),
        scenario=IRRBBScenario.PARALLEL_UP,
        resolver=resolver,
    )

    assert [item.position_id for item in result.projections] == ["p1", "p2"]
    assert [item.position_id for item in result.accruals] == ["p1", "p2"]
    assert resolver.calls == ["p1", "p2"]


def test_no_accrual_in_horizon_is_explicit_and_not_flattened() -> None:
    position = _position("p1")
    basis = _basis()
    projection = NIIPositionProjection(
        position_id=position.position_id,
        scenario=IRRBBScenario.BASE,
        basis=basis,
        strategy_reference="strategy:test-runoff",
        status=NIIPositionProjectionStatus.NO_ACCRUAL_IN_HORIZON,
        accruals=(),
    )

    batch = NIIProjectionBatch(
        basis=basis,
        scenario=IRRBBScenario.BASE,
        projections=(projection,),
    )

    assert batch.accruals == ()


def test_projected_status_rejects_unexplained_empty_accruals() -> None:
    with pytest.raises(ValueError, match="requires accruals"):
        NIIPositionProjection(
            position_id="p1",
            scenario=IRRBBScenario.BASE,
            basis=_basis(),
            strategy_reference="strategy:test",
            status=NIIPositionProjectionStatus.PROJECTED,
            accruals=(),
        )


def test_no_accrual_status_rejects_hidden_accruals() -> None:
    with pytest.raises(ValueError, match="cannot contain accruals"):
        NIIPositionProjection(
            position_id="p1",
            scenario=IRRBBScenario.BASE,
            basis=_basis(),
            strategy_reference="strategy:test",
            status=NIIPositionProjectionStatus.NO_ACCRUAL_IN_HORIZON,
            accruals=(
                _accrual(
                    position_id="p1",
                    scenario=IRRBBScenario.BASE,
                    accrual_id="a1",
                ),
            ),
        )


def test_position_projection_rejects_position_substitution_inside_accrual() -> None:
    with pytest.raises(ValueError, match="position_id must match"):
        NIIPositionProjection(
            position_id="p1",
            scenario=IRRBBScenario.BASE,
            basis=_basis(),
            strategy_reference="strategy:test",
            status=NIIPositionProjectionStatus.PROJECTED,
            accruals=(
                _accrual(
                    position_id="other",
                    scenario=IRRBBScenario.BASE,
                    accrual_id="a1",
                ),
            ),
        )


def test_projection_service_rejects_strategy_position_substitution() -> None:
    def substituted(position, basis, scenario):  # type: ignore[no-untyped-def]
        return NIIPositionProjection(
            position_id="other",
            scenario=scenario,
            basis=basis,
            strategy_reference="strategy:substituted-position",
            status=NIIPositionProjectionStatus.PROJECTED,
            accruals=(
                _accrual(
                    position_id="other",
                    scenario=scenario,
                    accrual_id="other:1",
                ),
            ),
        )

    with pytest.raises(ValueError, match="substituted position_id"):
        NIIProjectionService.project(
            positions=(_position("p1"),),
            basis=_basis(),
            scenario=IRRBBScenario.BASE,
            resolver=_Resolver(_Strategy(projection_factory=substituted)),
        )


def test_projection_service_rejects_strategy_scenario_substitution() -> None:
    def substituted(position, basis, scenario):  # type: ignore[no-untyped-def]
        projected = _projected(position, basis, IRRBBScenario.PARALLEL_DOWN)
        return projected

    with pytest.raises(ValueError, match="substituted scenario"):
        NIIProjectionService.project(
            positions=(_position("p1"),),
            basis=_basis(),
            scenario=IRRBBScenario.BASE,
            resolver=_Resolver(_Strategy(projection_factory=substituted)),
        )


def test_projection_service_rejects_strategy_basis_substitution() -> None:
    def substituted(position, basis, scenario):  # type: ignore[no-untyped-def]
        other_basis = replace(basis, horizon_end_date=date(2027, 8, 31))
        return _projected(position, other_basis, scenario)

    with pytest.raises(ValueError, match="substituted projection basis"):
        NIIProjectionService.project(
            positions=(_position("p1"),),
            basis=_basis(),
            scenario=IRRBBScenario.BASE,
            resolver=_Resolver(_Strategy(projection_factory=substituted)),
        )


def test_projection_service_rejects_duplicate_input_positions() -> None:
    with pytest.raises(ValueError, match="duplicate NII projection position_id"):
        NIIProjectionService.project(
            positions=(_position("p1"), _position("p1")),
            basis=_basis(),
            scenario=IRRBBScenario.BASE,
            resolver=_Resolver(_Strategy(projection_factory=_projected)),
        )


def test_batch_rejects_duplicate_accrual_ids_across_positions() -> None:
    basis = _basis()
    projections = tuple(
        NIIPositionProjection(
            position_id=position_id,
            scenario=IRRBBScenario.BASE,
            basis=basis,
            strategy_reference="strategy:test",
            status=NIIPositionProjectionStatus.PROJECTED,
            accruals=(
                _accrual(
                    position_id=position_id,
                    scenario=IRRBBScenario.BASE,
                    accrual_id="duplicate",
                ),
            ),
        )
        for position_id in ("p1", "p2")
    )

    with pytest.raises(ValueError, match="duplicate batch NII accrual_id"):
        NIIProjectionBatch(
            basis=basis,
            scenario=IRRBBScenario.BASE,
            projections=projections,
        )
