from __future__ import annotations

from aip.domain.irrbb.nii_audit_persistence_activation import (
    NIIRunAuditPersistenceActivationAuthorization,
    NIIRunAuditPersistenceActivationConfiguration,
    NIIRunAuditPersistenceActivationError,
)
from aip.domain.irrbb.nii_audit_persistence_readiness import (
    NIIAuditPersistenceReadinessAssessment,
)
from aip.domain.irrbb.nii_audit_serialization_compatibility import (
    NIIRunAuditSerializationCompatibilityCertificate,
)


class NIIRunAuditPersistenceActivationService:
    """Authorize one exact physical persistence configuration fail-closed."""

    @classmethod
    def authorize(
        cls,
        *,
        configuration: NIIRunAuditPersistenceActivationConfiguration,
        readiness: NIIAuditPersistenceReadinessAssessment,
        compatibility: NIIRunAuditSerializationCompatibilityCertificate,
    ) -> NIIRunAuditPersistenceActivationAuthorization:
        if not readiness.is_ready:
            raise NIIRunAuditPersistenceActivationError(
                "NII audit persistence activation is blocked by readiness assessment"
            )
        if readiness.adapter_reference != configuration.adapter_reference:
            raise NIIRunAuditPersistenceActivationError(
                "NII audit persistence activation adapter identity mismatch"
            )
        if compatibility.schema_contract != configuration.schema_contract:
            raise NIIRunAuditPersistenceActivationError(
                "NII audit persistence activation schema contract mismatch"
            )
        if compatibility.codec_reference != configuration.codec_reference:
            raise NIIRunAuditPersistenceActivationError(
                "NII audit persistence activation codec identity mismatch"
            )
        if compatibility.integrity_reference != configuration.integrity_reference:
            raise NIIRunAuditPersistenceActivationError(
                "NII audit persistence activation integrity identity mismatch"
            )
        return NIIRunAuditPersistenceActivationAuthorization(
            configuration=configuration,
            readiness=readiness,
            compatibility=compatibility,
        )
