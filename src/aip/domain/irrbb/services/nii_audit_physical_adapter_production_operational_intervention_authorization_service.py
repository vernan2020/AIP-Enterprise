from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation,
)


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationService:
    """Authorize, but never execute, one explicit operational intervention fail-closed."""

    @classmethod
    def authorize(
        cls,
        *,
        operational_status_attestation: (
            NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation
        ),
        authorization_reference: str,
        action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence],
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization:
        if not authorization_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError(
                "NII audit operational intervention authorization_reference is required"
            )
        if (
            operational_status_attestation.status
            is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError(
                "HEALTHY NII audit operational status cannot authorize intervention"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError(
                    "Duplicate NII audit operational intervention evidence requirement"
                )
            evidence_by_requirement[item.requirement] = item

        if (
            frozenset(evidence_by_requirement)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_REQUIREMENTS
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError(
                "NII audit operational intervention evidence must cover every required control"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization(
            operational_status_attestation=operational_status_attestation,
            authorization_reference=authorization_reference,
            action=action,
            evidence=canonical_evidence,
        )
