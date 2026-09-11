from __future__ import annotations

from aip.domain.irrbb.models import BankingBookPosition, IRRBBScenario
from aip.domain.irrbb.nii import NIIProjectionBasis
from aip.domain.irrbb.nii_projection import NIIProjectionBatch
from aip.domain.irrbb.ports import NIIProjectionStrategyResolver


class NIIProjectionService:
    """Orchestrate approved position strategies without embedding projection rules."""

    @classmethod
    def project(
        cls,
        *,
        positions: tuple[BankingBookPosition, ...],
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
        resolver: NIIProjectionStrategyResolver,
    ) -> NIIProjectionBatch:
        if not positions:
            raise ValueError("NII projection requires at least one position")

        seen_position_ids: set[str] = set()
        projections = []
        for position in positions:
            if position.position_id in seen_position_ids:
                raise ValueError(f"duplicate NII projection position_id: {position.position_id}")
            seen_position_ids.add(position.position_id)

            strategy = resolver.resolve(position=position)
            projection = strategy.project(
                position=position,
                basis=basis,
                scenario=scenario,
            )
            if projection.position_id != position.position_id:
                raise ValueError("NII projection strategy substituted position_id")
            if projection.scenario is not scenario:
                raise ValueError("NII projection strategy substituted scenario")
            if projection.basis != basis:
                raise ValueError("NII projection strategy substituted projection basis")
            projections.append(projection)

        return NIIProjectionBatch(
            basis=basis,
            scenario=scenario,
            projections=tuple(projections),
        )
