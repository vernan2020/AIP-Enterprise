from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_continuity_epoch import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_CONTINUITY_EPOCH_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch,
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError,
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)


class NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochService:
    """Open one new governed steady-state epoch after accepted operational recovery."""

    @classmethod
    def record(
        cls,
        *,
        recovery_acceptance: NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance,
        epoch_reference: str,
        evidence: Iterable[
            NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch:
        if (
            recovery_acceptance.recovery_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError(
                "NII audit operational continuity epoch requires a successful recovery receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
            for result in recovery_acceptance.recovery_receipt.checkpoint_results
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError(
                "NII audit operational continuity epoch requires every recovery checkpoint to succeed"
            )
        if not epoch_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError(
                "NII audit operational continuity epoch_reference is required"
            )
        if epoch_reference == recovery_acceptance.operations_reference:
            raise NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError(
                "NII audit operational continuity epoch_reference must differ from the previous "
                "steady-state operations_reference"
            )

        evidence_items = tuple(evidence)
        by_requirement = {}
        for item in evidence_items:
            if item.requirement in by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError(
                    "Duplicate NII audit operational continuity epoch evidence requirement"
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
            raise NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochError(
                "NII audit operational continuity epoch evidence must cover every required control"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch(
            recovery_acceptance=recovery_acceptance,
            epoch_reference=epoch_reference,
            evidence=canonical_evidence,
        )
