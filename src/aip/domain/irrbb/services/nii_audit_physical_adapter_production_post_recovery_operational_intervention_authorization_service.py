from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_reattestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_authorization import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_POST_RECOVERY_OPERATIONAL_INTERVENTION_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService:
    """Authorize, but never execute, one intervention for a post-recovery continuity epoch."""

    @classmethod
    def authorize(
        cls,
        *,
        operational_status_reattestation: (
            NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation
        ),
        authorization_reference: str,
        action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
        evidence: Iterable[
            NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization:
        if not authorization_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
                "NII audit post-recovery intervention authorization_reference is required"
            )
        if not operational_status_reattestation.reattestation_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
                "NII audit post-recovery intervention requires a valid status re-attestation"
            )
        if (
            operational_status_reattestation.status
            is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
                "HEALTHY NII audit post-recovery operational status cannot authorize intervention"
            )
        if not operational_status_reattestation.exception_references:
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
                "Non-HEALTHY NII audit post-recovery operational status requires exceptions"
            )
        if not operational_status_reattestation.epoch_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
                "NII audit post-recovery intervention requires a valid continuity epoch"
            )
        if (
            operational_status_reattestation.epoch_reference
            == operational_status_reattestation.previous_operations_reference
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
                "NII audit post-recovery intervention requires a distinct continuity epoch"
            )
        if (
            authorization_reference
            == operational_status_reattestation.intervention_authorization_reference
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
                "NII audit post-recovery intervention cannot reuse the previous authorization_reference"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
                    "Duplicate NII audit post-recovery intervention evidence requirement"
                )
            evidence_by_requirement[item.requirement] = item

        if (
            frozenset(evidence_by_requirement)
            != REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_POST_RECOVERY_OPERATIONAL_INTERVENTION_REQUIREMENTS
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationError(
                "NII audit post-recovery intervention evidence must cover every required control"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization(
            operational_status_reattestation=operational_status_reattestation,
            authorization_reference=authorization_reference,
            action=action,
            evidence=canonical_evidence,
        )
