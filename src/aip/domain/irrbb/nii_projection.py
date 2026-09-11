from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.models import IRRBBScenario
from aip.domain.irrbb.nii import NIIInterestAccrual, NIIProjectionBasis


class NIIPositionProjectionStatus(str, Enum):
    """Outcome of one position-level NII projection strategy."""

    PROJECTED = "PROJECTED"
    NO_ACCRUAL_IN_HORIZON = "NO_ACCRUAL_IN_HORIZON"


@dataclass(frozen=True, slots=True)
class NIIPositionProjection:
    """Auditable result returned by one approved position projection strategy.

    ``PROJECTED`` requires at least one explicit accrual. A legitimate position with
    no interest accrual inside the requested horizon must use
    ``NO_ACCRUAL_IN_HORIZON`` instead of returning an unexplained empty tuple.
    """

    position_id: str
    scenario: IRRBBScenario
    basis: NIIProjectionBasis
    strategy_reference: str
    status: NIIPositionProjectionStatus
    accruals: tuple[NIIInterestAccrual, ...]

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("NII projection position_id is required")
        if not self.strategy_reference.strip():
            raise ValueError("NII projection strategy_reference is required")

        if self.status is NIIPositionProjectionStatus.PROJECTED and not self.accruals:
            raise ValueError("PROJECTED NII position projection requires accruals")
        if (
            self.status is NIIPositionProjectionStatus.NO_ACCRUAL_IN_HORIZON
            and self.accruals
        ):
            raise ValueError("NO_ACCRUAL_IN_HORIZON projection cannot contain accruals")

        seen_accrual_ids: set[str] = set()
        for accrual in self.accruals:
            if accrual.accrual_id in seen_accrual_ids:
                raise ValueError(
                    f"duplicate position-level NII accrual_id: {accrual.accrual_id}"
                )
            seen_accrual_ids.add(accrual.accrual_id)
            if accrual.position_id != self.position_id:
                raise ValueError("NII projection accrual position_id must match position")
            if accrual.scenario is not self.scenario:
                raise ValueError("NII projection accrual scenario must match projection")
            if accrual.accrual_start_date < self.basis.valuation_date:
                raise ValueError("NII projection accrual starts before valuation_date")
            if accrual.accrual_end_date > self.basis.horizon_end_date:
                raise ValueError("NII projection accrual ends after projection horizon")


@dataclass(frozen=True, slots=True)
class NIIProjectionBatch:
    """Validated collection of position-level projections for one scenario."""

    basis: NIIProjectionBasis
    scenario: IRRBBScenario
    projections: tuple[NIIPositionProjection, ...]

    def __post_init__(self) -> None:
        if not self.projections:
            raise ValueError("NII projection batch requires at least one position")

        seen_position_ids: set[str] = set()
        seen_accrual_ids: set[str] = set()
        for projection in self.projections:
            if projection.position_id in seen_position_ids:
                raise ValueError(
                    f"duplicate NII projection position_id: {projection.position_id}"
                )
            seen_position_ids.add(projection.position_id)
            if projection.scenario is not self.scenario:
                raise ValueError("position projection scenario must match batch scenario")
            if projection.basis != self.basis:
                raise ValueError("position projection basis must match batch basis")

            for accrual in projection.accruals:
                if accrual.accrual_id in seen_accrual_ids:
                    raise ValueError(f"duplicate batch NII accrual_id: {accrual.accrual_id}")
                seen_accrual_ids.add(accrual.accrual_id)

    @property
    def accruals(self) -> tuple[NIIInterestAccrual, ...]:
        """Flatten explicit accruals without manufacturing zero-value records."""

        return tuple(
            accrual
            for projection in self.projections
            for accrual in projection.accruals
        )
