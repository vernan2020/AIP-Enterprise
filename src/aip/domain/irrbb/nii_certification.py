from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.models import IRRBBScenario
from aip.domain.irrbb.nii import NIIProjectionBasis
from aip.domain.irrbb.nii_projection import NIIProjectionBatch
from aip.domain.irrbb.nii_readiness import (
    NIIProjectionReadinessAssessment,
    NIIProjectionReadinessStatus,
)


class NIIProjectionCertificationStatus(str, Enum):
    """Portfolio-level outcome of readiness certification plus projection."""

    PROJECTED = "PROJECTED"
    BLOCKED = "BLOCKED"
    NO_INCLUDED_POSITIONS = "NO_INCLUDED_POSITIONS"


@dataclass(frozen=True, slots=True)
class NIIProjectionCertificationResult:
    """Auditable result of portfolio-level NII projection certification.

    A blocked included position prevents every strategy from being executed. Fully
    excluded portfolios are explicit and do not manufacture an empty projection
    batch. A projected result must cover exactly the positions certified READY.
    """

    basis: NIIProjectionBasis
    scenario: IRRBBScenario
    status: NIIProjectionCertificationStatus
    assessments: tuple[NIIProjectionReadinessAssessment, ...]
    projection_batch: NIIProjectionBatch | None = None

    def __post_init__(self) -> None:
        if not self.assessments:
            raise ValueError("NII projection certification requires assessments")

        position_ids = tuple(item.position_id for item in self.assessments)
        if len(set(position_ids)) != len(position_ids):
            raise ValueError("duplicate NII projection certification position_id")

        blocked = tuple(
            item
            for item in self.assessments
            if item.status is NIIProjectionReadinessStatus.BLOCKED
        )
        ready = tuple(
            item
            for item in self.assessments
            if item.status is NIIProjectionReadinessStatus.READY
        )
        excluded = tuple(
            item
            for item in self.assessments
            if item.status is NIIProjectionReadinessStatus.EXCLUDED
        )

        if self.status is NIIProjectionCertificationStatus.BLOCKED:
            if not blocked:
                raise ValueError("BLOCKED NII certification requires a blocked assessment")
            if self.projection_batch is not None:
                raise ValueError("BLOCKED NII certification cannot contain projections")
            return

        if self.status is NIIProjectionCertificationStatus.NO_INCLUDED_POSITIONS:
            if len(excluded) != len(self.assessments):
                raise ValueError(
                    "NO_INCLUDED_POSITIONS requires every assessment to be EXCLUDED"
                )
            if self.projection_batch is not None:
                raise ValueError("excluded-only NII certification cannot contain projections")
            return

        if blocked:
            raise ValueError("PROJECTED NII certification cannot contain blocked assessments")
        if not ready:
            raise ValueError("PROJECTED NII certification requires at least one READY position")
        if self.projection_batch is None:
            raise ValueError("PROJECTED NII certification requires projection_batch")
        if self.projection_batch.basis != self.basis:
            raise ValueError("NII certification projection batch substituted projection basis")
        if self.projection_batch.scenario is not self.scenario:
            raise ValueError("NII certification projection batch substituted scenario")

        projections_by_position = {
            projection.position_id: projection
            for projection in self.projection_batch.projections
        }
        ready_by_position = {item.position_id: item for item in ready}
        if projections_by_position.keys() != ready_by_position.keys():
            raise ValueError("NII certification projections must cover exactly READY positions")

        for position_id, assessment in ready_by_position.items():
            projection = projections_by_position[position_id]
            if projection.strategy_reference != assessment.strategy_reference:
                raise ValueError(
                    "NII certification projection strategy_reference does not match profile"
                )
