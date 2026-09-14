from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceService:
    """Accept one exact successful externally observed Phase 59 intervention."""

    @classmethod
    def accept(
        cls,
        *,
        intervention_receipt: (
            NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt
        ),
        acceptance_reference: str,
        evidence: Iterable[
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance:
        if (
            intervention_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError(
                "NII audit post-recovery intervention acceptance requires a successful receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
            for result in intervention_receipt.checkpoint_results
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError(
                "NII audit post-recovery intervention acceptance requires every checkpoint to succeed"
            )
        if (
            intervention_receipt.authorization_reference
            == intervention_receipt.previous_intervention_authorization_reference
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError(
                "NII audit post-recovery intervention acceptance requires a distinct authorization cycle"
            )
        if not acceptance_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError(
                "NII audit post-recovery intervention acceptance_reference is required"
            )

        evidence_items = tuple(evidence)
        by_requirement = {}
        for item in evidence_items:
            if item.requirement in by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError(
                    "Duplicate NII audit post-recovery intervention acceptance evidence requirement"
                )
            by_requirement[item.requirement] = item

        missing = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS
            - set(by_requirement)
        )
        unexpected = set(by_requirement) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS
        )
        if missing or unexpected:
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError(
                "NII audit post-recovery intervention acceptance evidence must cover every "
                "required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance(
            intervention_receipt=intervention_receipt,
            acceptance_reference=acceptance_reference,
            evidence=canonical_evidence,
        )
