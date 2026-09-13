from __future__ import annotations

from aip.domain.irrbb.nii_audit_persistence_activation import (
    NIIRunAuditPersistenceActivationAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_persistence import (
    NIIRunAuditActivatedPhysicalPersistence,
    NIIRunAuditPhysicalPersistenceActivationError,
    NIIRunAuditPhysicalPersistenceAdapter,
)


class NIIRunAuditPhysicalPersistenceActivationService:
    """Bind one authorized configuration to one exact physical adapter fail-closed."""

    @classmethod
    def activate(
        cls,
        *,
        authorization: NIIRunAuditPersistenceActivationAuthorization,
        adapter: NIIRunAuditPhysicalPersistenceAdapter,
    ) -> NIIRunAuditActivatedPhysicalPersistence:
        configuration = authorization.configuration
        descriptor = adapter.descriptor

        if descriptor.adapter_reference != configuration.adapter_reference:
            raise NIIRunAuditPhysicalPersistenceActivationError(
                "NII audit physical persistence adapter identity mismatch"
            )
        if descriptor.schema_contract != configuration.schema_contract:
            raise NIIRunAuditPhysicalPersistenceActivationError(
                "NII audit physical persistence schema contract mismatch"
            )
        if descriptor.codec_reference != configuration.codec_reference:
            raise NIIRunAuditPhysicalPersistenceActivationError(
                "NII audit physical persistence codec identity mismatch"
            )
        if descriptor.integrity_reference != configuration.integrity_reference:
            raise NIIRunAuditPhysicalPersistenceActivationError(
                "NII audit physical persistence integrity identity mismatch"
            )

        repository = adapter.activate(authorization=authorization)
        return NIIRunAuditActivatedPhysicalPersistence(
            authorization=authorization,
            descriptor=descriptor,
            repository=repository,
        )
