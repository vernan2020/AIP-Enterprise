from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_acceptance import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_ACCEPTANCE_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)


class NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceService:
    """Accept one exact successful externally observed return-to-service attempt."""

    @classmethod
    def accept(
        cls,
        *,
        recovery_receipt: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt,
        acceptance_reference: str,
        evidence: Iterable[
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance:
        if (
            recovery_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError(
                "NII audit operational recovery acceptance requires a successful receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
            for result in recovery_receipt.checkpoint_results
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError(
                "NII audit operational recovery acceptance requires every checkpoint to succeed"
            )
        if not acceptance_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError(
                "NII audit operational recovery acceptance_reference is required"
            )

        evidence_items = tuple(evidence)
        by_requirement = {}
        for item in evidence_items:
            if item.requirement in by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError(
                    "Duplicate NII audit operational recovery acceptance evidence requirement"
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
            raise NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError(
                "NII audit operational recovery acceptance evidence must cover every required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance(
            recovery_receipt=recovery_receipt,
            acceptance_reference=acceptance_reference,
            evidence=canonical_evidence,
        )
