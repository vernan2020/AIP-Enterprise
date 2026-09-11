from __future__ import annotations

from aip.domain.irrbb.nii_run_audit import (
    NIIRunAuditConflictError,
    NIIRunAuditRecord,
    NIIRunAuditWriteResult,
    NIIRunAuditWriteStatus,
)
from aip.domain.irrbb.ports import NIIRunAuditRepository
from aip.domain.irrbb.services.nii_run_reproducibility_service import (
    NIIRunReproducibilityService,
)


class NIIRunAuditService:
    """Persist and retrieve immutable NII run audit records fail-closed."""

    def __init__(self, *, repository: NIIRunAuditRepository) -> None:
        self._repository = repository

    def store(self, *, record: NIIRunAuditRecord) -> NIIRunAuditWriteResult:
        self._validate_record(record)
        repository_result = self._repository.put_if_absent(record=record)

        if repository_result.record.run_reference != record.run_reference:
            raise RuntimeError("NII audit repository substituted run_reference")

        if repository_result.created:
            if repository_result.record != record:
                raise RuntimeError("NII audit repository substituted newly stored record")
            return NIIRunAuditWriteResult(
                status=NIIRunAuditWriteStatus.STORED,
                record=record,
            )

        if repository_result.record == record:
            return NIIRunAuditWriteResult(
                status=NIIRunAuditWriteStatus.IDEMPOTENT,
                record=record,
            )

        existing = repository_result.record
        if existing.specification_fingerprint != record.specification_fingerprint:
            reason = "methodology fingerprint differs"
        else:
            reason = "audit payload differs"
        raise NIIRunAuditConflictError(
            f"NII audit run_reference {record.run_reference!r} already exists and {reason}"
        )

    def get(self, *, run_reference: str) -> NIIRunAuditRecord | None:
        if not run_reference.strip():
            raise ValueError("NII audit run_reference is required")
        record = self._repository.get_by_run_reference(run_reference=run_reference)
        if record is None:
            return None
        if record.run_reference != run_reference:
            raise RuntimeError("NII audit repository substituted lookup run_reference")
        self._validate_record(record)
        return record

    @staticmethod
    def _validate_record(record: NIIRunAuditRecord) -> None:
        expected_manifest = NIIRunReproducibilityService.build(
            specification=record.specification
        )
        if record.manifest != expected_manifest:
            raise ValueError("NII audit manifest does not match methodology run specification")
