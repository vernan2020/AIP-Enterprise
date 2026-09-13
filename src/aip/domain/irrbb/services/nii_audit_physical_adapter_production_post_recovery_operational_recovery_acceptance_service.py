from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_acceptance import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_ACCEPTANCE_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceService:
    """Accept one exact successful post-recovery operational recovery receipt."""

    @classmethod
    def accept(
        cls,
        *,
        recovery_receipt: NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
        acceptance_reference: str,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence],
    ) -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance:
        if (
            recovery_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError(
                "NII audit post-recovery operational recovery acceptance requires a successful receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
            for result in recovery_receipt.checkpoint_results
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError(
                "NII audit post-recovery operational recovery acceptance requires every checkpoint to succeed"
            )
        if (
            recovery_receipt.authorization_reference
            == recovery_receipt.previous_recovery_authorization_reference
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError(
                "NII audit post-recovery operational recovery acceptance requires a distinct recovery cycle"
            )
        if not acceptance_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError(
                "NII audit post-recovery operational recovery acceptance_reference is required"
            )

        evidence_items = tuple(evidence)
        by_requirement = {}
        for item in evidence_items:
            if item.requirement in by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError(
                    "Duplicate NII audit post-recovery operational recovery acceptance evidence requirement"
                )
            by_requirement[item.requirement] = item

        missing = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_ACCEPTANCE_REQUIREMENTS
            - set(by_requirement)
        )
        unexpected = set(by_requirement) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_ACCEPTANCE_REQUIREMENTS
        )
        if missing or unexpected:
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError(
                "NII audit post-recovery operational recovery acceptance evidence must cover every required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance(
            recovery_receipt=recovery_receipt,
            acceptance_reference=acceptance_reference,
            evidence=canonical_evidence,
        )
