from __future__ import annotations

from typing import Protocol

from aip.domain.irrbb.nii_run_audit import (
    NIIRunAuditRecord,
    NIIRunAuditRepositoryPutResult,
)


class NIIRunAuditRepository(Protocol):
    """Source-neutral immutable persistence boundary for audited NII runs."""

    def get_by_run_reference(self, *, run_reference: str) -> NIIRunAuditRecord | None: ...

    def put_if_absent(
        self,
        *,
        record: NIIRunAuditRecord,
    ) -> NIIRunAuditRepositoryPutResult: ...
