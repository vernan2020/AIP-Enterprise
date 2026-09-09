from __future__ import annotations

from datetime import date
from typing import Protocol

from aip.application.irrbb.contracts import IRRBBSourceSnapshot


class IRRBBDataGateway(Protocol):
    """Application port for a fully normalized RTILB/IRRBB source snapshot.

    Implementations may read XML, SQL Server, PostgreSQL, Excel/OneDrive or any
    approved source. They must normalize source-specific fields before returning
    the snapshot and must not perform EVE, Delta EVE or SUGEF GAP calculations.
    """

    def load_snapshot(self, *, cutoff_date: date) -> IRRBBSourceSnapshot: ...
