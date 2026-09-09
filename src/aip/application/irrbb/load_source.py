from __future__ import annotations

from aip.application.irrbb.contracts import (
    IRRBBSourceLoadRequest,
    IRRBBSourceLoadResult,
    IRRBBSourceLoadStatus,
)
from aip.application.irrbb.ports import IRRBBDataGateway
from aip.domain.irrbb.data_quality import IRRBBDataQualityStatus
from aip.domain.irrbb.services.data_quality_service import IRRBBPositionDataQualityService


class LoadIRRBBSourceSnapshot:
    """Load and assess one normalized RTILB source snapshot.

    This use case deliberately stops before economic-value or SUGEF GAP calculation.
    Its responsibility is to establish the canonical source perimeter, validate the
    requested cutoff and expose which positions are calculation-ready, incomplete or
    excluded under the capabilities declared by the gateway.
    """

    def __init__(self, gateway: IRRBBDataGateway) -> None:
        self._gateway = gateway

    def execute(self, request: IRRBBSourceLoadRequest) -> IRRBBSourceLoadResult:
        snapshot = self._gateway.load_snapshot(cutoff_date=request.cutoff_date)
        if snapshot.cutoff_date != request.cutoff_date:
            raise ValueError("IRRBB data gateway returned a snapshot for a different cutoff date")

        assessments = tuple(
            IRRBBPositionDataQualityService.assess(
                position=record.position,
                valuation_date=request.cutoff_date,
                context=record.validation_context,
            )
            for record in snapshot.position_records
        )

        ready = tuple(
            assessment.position_id
            for assessment in assessments
            if assessment.status is IRRBBDataQualityStatus.READY
        )
        incomplete = tuple(
            assessment.position_id
            for assessment in assessments
            if assessment.status is IRRBBDataQualityStatus.INCOMPLETE
        )
        excluded = tuple(
            assessment.position_id
            for assessment in assessments
            if assessment.status is IRRBBDataQualityStatus.EXCLUDED
        )

        return IRRBBSourceLoadResult(
            snapshot=snapshot,
            assessments=assessments,
            status=self._status(
                position_count=len(snapshot.position_records),
                ready_count=len(ready),
                incomplete_count=len(incomplete),
            ),
            ready_position_ids=ready,
            incomplete_position_ids=incomplete,
            excluded_position_ids=excluded,
        )

    @staticmethod
    def _status(
        *,
        position_count: int,
        ready_count: int,
        incomplete_count: int,
    ) -> IRRBBSourceLoadStatus:
        if position_count == 0:
            return IRRBBSourceLoadStatus.EMPTY
        if ready_count == position_count:
            return IRRBBSourceLoadStatus.READY
        if ready_count > 0:
            return IRRBBSourceLoadStatus.PARTIAL
        if incomplete_count > 0:
            return IRRBBSourceLoadStatus.BLOCKED
        return IRRBBSourceLoadStatus.BLOCKED
