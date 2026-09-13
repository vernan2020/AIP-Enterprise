from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence,
)


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationService:
    """Authorize one exact return-to-service action without executing it."""

    @classmethod
    def authorize(
        cls,
        *,
        intervention_acceptance: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance,
        authorization_reference: str,
        action: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence],
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization:
        if not authorization_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError(
                "NII audit operational recovery authorization_reference is required"
            )

        expected_action = {
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND: (
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
            ),
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.DEACTIVATE: (
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.REACTIVATE
            ),
        }[intervention_acceptance.action]
        if action is not expected_action:
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError(
                "NII audit operational recovery action must match the accepted intervention action"
            )

        evidence_items = tuple(evidence)
        by_requirement = {}
        for item in evidence_items:
            if item.requirement in by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError(
                    "Duplicate NII audit operational recovery evidence requirement"
                )
            by_requirement[item.requirement] = item

        missing = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_REQUIREMENTS
            - set(by_requirement)
        )
        unexpected = set(by_requirement) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_REQUIREMENTS
        )
        if missing or unexpected:
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationError(
                "NII audit operational recovery evidence must cover every required control"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization(
            intervention_acceptance=intervention_acceptance,
            authorization_reference=authorization_reference,
            action=action,
            evidence=canonical_evidence,
        )
