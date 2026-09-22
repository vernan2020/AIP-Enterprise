from __future__ import annotations

from datetime import date
from typing import Protocol

from aip.application.irrbb.analysis_contracts import IRRBBAnalysisRequest
from aip.application.irrbb.contracts import IRRBBSourceSnapshot
from aip.application.irrbb.credit_gap_schedule_contracts import (
    IRRBBCreditGapScheduleSnapshot,
)


class IRRBBDataGateway(Protocol):
    """Application port for a fully normalized RTILB/IRRBB source snapshot.

    Implementations may read XML, SQL Server, PostgreSQL, Excel/OneDrive or any
    approved source. They must normalize source-specific fields before returning
    the snapshot and must not perform EVE, Delta EVE or SUGEF GAP calculations.
    """

    def load_snapshot(self, *, cutoff_date: date) -> IRRBBSourceSnapshot: ...


class IRRBBAnalysisRequestProvider(Protocol):
    """Provide the approved RTILB methodology/request for one valuation cutoff.

    The provider owns configuration of reporting currency, methodology version and
    required stress scenarios. UI and composition code must not manufacture those
    regulatory parameters.
    """

    def request_for(self, *, cutoff_date: date) -> IRRBBAnalysisRequest: ...


class IRRBBCreditGapScheduleGateway(Protocol):
    """Application port for an explicit contractual Credit GAP schedule complement.

    Implementations may use any approved physical source, but they must return one
    auditable outcome for every requested operation and must not infer installments
    or manufacture residual principal.
    """

    def load_schedule_snapshot(
        self,
        *,
        cutoff_date: date,
        operation_ids: tuple[str, ...],
    ) -> IRRBBCreditGapScheduleSnapshot: ...
