from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_continuity_epoch import (
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_continuity_epoch import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpoch,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_post_recovery_operational_continuity_epoch_service import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochService,
)


class _RecoveryReceiptStub:
    status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
    checkpoint_results = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
            checkpoint=checkpoint,
            status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED,
            evidence_reference=f"observed:{checkpoint.value.lower()}",
        )
        for checkpoint in NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
    )


class _RecoveryAcceptanceStub:
    recovery_receipt = _RecoveryReceiptStub()
    acceptance_reference = "recovery-acceptance:post-recovery:64"
    recovery_receipt_reference = "recovery-receipt:post-recovery:64"
    recovery_reference = "recovery-execution:post-recovery:64"
    recovery_authorization_reference = "recovery-auth:post-recovery:64"
    recovery_action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    epoch_reference = "steady-state:previous:64"
    reattestation_reference = "status-reattestation:64"
    operational_status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
    intervention_acceptance_reference = "intervention-acceptance:post-recovery:64"
    intervention_authorization_reference = "intervention-auth:post-recovery:64"
    intervention_action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    previous_recovery_authorization_reference = "recovery-auth:previous:64"
    previous_operations_reference = "steady-state:pre-recovery:64"
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _acceptance() -> (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance
):
    return cast(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance,
        _RecoveryAcceptanceStub(),
    )


def _evidence() -> tuple[
    NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence, ...
]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochEvidence(
            requirement=requirement,
            source_reference=f"continuity:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement)
        )
    )


def test_record_preserves_exact_acceptance_and_full_chain() -> None:
    acceptance = _acceptance()
    epoch = NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochService.record(
        recovery_acceptance=acceptance,
        epoch_reference="steady-state:new:64",
        evidence=_evidence(),
    )

    assert epoch.recovery_acceptance is acceptance
    assert epoch.recovery_acceptance_reference == acceptance.acceptance_reference
    assert epoch.recovery_receipt_reference == acceptance.recovery_receipt_reference
    assert epoch.recovery_authorization_reference == acceptance.recovery_authorization_reference
    assert epoch.recovery_action is acceptance.recovery_action
    assert epoch.previous_epoch_reference == acceptance.epoch_reference
    assert epoch.reattestation_reference == acceptance.reattestation_reference
    assert epoch.intervention_authorization_reference == acceptance.intervention_authorization_reference
    assert epoch.adapter_reference == acceptance.adapter_reference
    assert tuple(item.requirement.value for item in epoch.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpochRequirement
        )
    )


def test_previous_epoch_reference_cannot_be_reused() -> None:
    acceptance = _acceptance()
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError,
        match="must differ",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochService.record(
            recovery_acceptance=acceptance,
            epoch_reference=acceptance.epoch_reference,
            evidence=_evidence(),
        )


def test_blank_epoch_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError,
        match="epoch_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochService.record(
            recovery_acceptance=_acceptance(),
            epoch_reference=" ",
            evidence=_evidence(),
        )


def test_failed_recovery_receipt_is_rejected() -> None:
    class _FailedAcceptance(_RecoveryAcceptanceStub):
        class _FailedReceipt(_RecoveryReceiptStub):
            status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.FAILED

        recovery_receipt = _FailedReceipt()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError,
        match="successful recovery receipt",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochService.record(
            recovery_acceptance=cast(
                NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance,
                _FailedAcceptance(),
            ),
            epoch_reference="steady-state:failed:64",
            evidence=_evidence(),
        )


def test_missing_or_duplicate_requirement_is_rejected() -> None:
    evidence = _evidence()
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError,
        match="cover every required control",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochService.record(
            recovery_acceptance=_acceptance(),
            epoch_reference="steady-state:missing:64",
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpochService.record(
            recovery_acceptance=_acceptance(),
            epoch_reference="steady-state:duplicate:64",
            evidence=(*evidence, evidence[0]),
        )


def test_direct_epoch_requires_canonical_evidence() -> None:
    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalContinuityEpoch(
            recovery_acceptance=_acceptance(),
            epoch_reference="steady-state:direct:64",
            evidence=_evidence(),
        )
