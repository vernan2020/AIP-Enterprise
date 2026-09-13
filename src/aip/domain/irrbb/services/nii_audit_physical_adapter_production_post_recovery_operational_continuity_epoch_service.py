from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_continuity_epoch import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_CONTINUITY_EPOCH_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_continuity_epoch import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpoch,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance,
)


class NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochService:
    """Record one new governed steady-state epoch after accepted second recovery."""

    @classmethod
    def record(
        cls,
        *,
        recovery_acceptance: (
            NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance
        ),
        epoch_reference: str,
        evidence: Iterable[
            NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpoch:
        if (
            recovery_acceptance.recovery_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError(
                "NII audit post-recovery continuity epoch requires a successful recovery receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
            for result in recovery_acceptance.recovery_receipt.checkpoint_results
        ):
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError(
                "NII audit post-recovery continuity epoch requires every recovery checkpoint to succeed"
            )
        if not epoch_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError(
                "NII audit post-recovery continuity epoch_reference is required"
            )
        if epoch_reference == recovery_acceptance.epoch_reference:
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError(
                "NII audit post-recovery continuity epoch_reference must differ from the previous epoch_reference"
            )

        evidence_items = tuple(evidence)
        by_requirement = {}
        for item in evidence_items:
            if item.requirement in by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError(
                    "Duplicate NII audit post-recovery continuity epoch evidence requirement"
                )
            by_requirement[item.requirement] = item

        missing = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_CONTINUITY_EPOCH_REQUIREMENTS
            - set(by_requirement)
        )
        unexpected = set(by_requirement) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_CONTINUITY_EPOCH_REQUIREMENTS
        )
        if missing or unexpected:
            raise NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError(
                "NII audit post-recovery continuity epoch evidence must cover every required control"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpoch(
            recovery_acceptance=recovery_acceptance,
            epoch_reference=epoch_reference,
            evidence=canonical_evidence,
        )
