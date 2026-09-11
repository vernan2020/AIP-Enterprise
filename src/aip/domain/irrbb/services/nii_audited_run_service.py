from __future__ import annotations

from aip.domain.irrbb.models import BankingBookPosition
from aip.domain.irrbb.nii_run_audit import (
    NIIRunAuditConflictError,
    NIIRunAuditRecord,
    NIIRunAuditWriteResult,
    NIIRunAuditWriteStatus,
)
from aip.domain.irrbb.nii_run_audit_ports import NIIRunAuditRepository
from aip.domain.irrbb.nii_run_specification import NIIMethodologyRunSpecification
from aip.domain.irrbb.ports import (
    NIIExchangeRateProvider,
    NIIProjectionCapabilityEvidenceProvider,
    NIIProjectionRequirementProfileProvider,
    NIIProjectionStrategyResolver,
)
from aip.domain.irrbb.services.nii_methodology_run_service import NIIMethodologyRunService
from aip.domain.irrbb.services.nii_run_audit_service import NIIRunAuditService
from aip.domain.irrbb.services.nii_run_reproducibility_service import (
    NIIRunReproducibilityService,
)


class NIIAuditedRunService:
    """Execute one governed NII run once and persist its immutable audit bundle."""

    def __init__(self, *, repository: NIIRunAuditRepository) -> None:
        self._audit = NIIRunAuditService(repository=repository)

    def execute(
        self,
        *,
        positions: tuple[BankingBookPosition, ...],
        specification: NIIMethodologyRunSpecification,
        profile_provider: NIIProjectionRequirementProfileProvider,
        capability_provider: NIIProjectionCapabilityEvidenceProvider,
        strategy_resolver: NIIProjectionStrategyResolver,
        exchange_rates: NIIExchangeRateProvider | None = None,
    ) -> NIIRunAuditWriteResult:
        existing = self._audit.get(run_reference=specification.run_reference)
        if existing is not None:
            if existing.specification != specification:
                raise NIIRunAuditConflictError(
                    f"NII audit run_reference {specification.run_reference!r} already exists "
                    "with a different methodology run specification"
                )
            return NIIRunAuditWriteResult(
                status=NIIRunAuditWriteStatus.IDEMPOTENT,
                record=existing,
            )

        result = NIIMethodologyRunService.execute(
            positions=positions,
            specification=specification,
            profile_provider=profile_provider,
            capability_provider=capability_provider,
            strategy_resolver=strategy_resolver,
            exchange_rates=exchange_rates,
        )
        manifest = NIIRunReproducibilityService.build(specification=specification)
        record = NIIRunAuditRecord(
            specification=specification,
            manifest=manifest,
            result=result,
        )
        return self._audit.store(record=record)
