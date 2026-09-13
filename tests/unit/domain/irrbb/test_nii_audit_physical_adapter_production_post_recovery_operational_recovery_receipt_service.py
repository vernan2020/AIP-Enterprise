from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_post_recovery_operational_recovery_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptService,
)


class _RecoveryAuthorizationStub:
    authorization_reference = "recovery-auth:new-cycle:62"
    action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    intervention_acceptance_reference = "intervention-acceptance:post-recovery:62"
    intervention_receipt_reference = "intervention-receipt:post-recovery:62"
    intervention_reference = "intervention-execution:post-recovery:62"
    intervention_authorization_reference = "intervention-auth:post-recovery:62"
    intervention_action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    reattestation_reference = "status-reattestation:degraded:62"
    operational_status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
    epoch_reference = "steady-state:post-recovery:62"
    previous_operations_reference = "steady-state:pre-recovery:62"
    previous_attestation_reference = "status:pre-recovery:62"
    previous_recovery_acceptance_reference = "recovery-acceptance:previous:62"
    previous_recovery_receipt_reference = "recovery-receipt:previous:62"
    previous_recovery_reference = "recovery-execution:previous:62"
    previous_recovery_authorization_reference = "recovery-auth:previous:62"
    previous_recovery_action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    previous_intervention_authorization_reference = "intervention-auth:previous:62"
    previous_intervention_action = (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _authorization() -> (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization
):
    return cast(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization,
        _RecoveryAuthorizationStub(),
    )


def _checkpoint_results(
    *,
    failed_checkpoint: (
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint | None
    ) = None,
) -> tuple[NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult, ...]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
            checkpoint=checkpoint,
            status=(
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.FAILED
                if checkpoint is failed_checkpoint
                else NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
            ),
            evidence_reference=f"observed:post-recovery:{checkpoint.value.lower()}:62",
        )
        for checkpoint in reversed(
            NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
        )
    )


def test_receipt_preserves_exact_authorization_and_full_chain() -> None:
    authorization = _authorization()

    receipt = (
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptService.record(
            recovery_authorization=authorization,
            receipt_reference="recovery-receipt:new-cycle:62",
            recovery_reference="recovery-execution:new-cycle:62",
            checkpoint_results=_checkpoint_results(),
        )
    )

    assert receipt.recovery_authorization is authorization
    assert receipt.status is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
    assert receipt.authorization_reference == authorization.authorization_reference
    assert receipt.action is authorization.action
    assert (
        receipt.intervention_acceptance_reference == authorization.intervention_acceptance_reference
    )
    assert receipt.intervention_receipt_reference == authorization.intervention_receipt_reference
    assert receipt.intervention_reference == authorization.intervention_reference
    assert (
        receipt.intervention_authorization_reference
        == authorization.intervention_authorization_reference
    )
    assert receipt.intervention_action is authorization.intervention_action
    assert receipt.reattestation_reference == authorization.reattestation_reference
    assert receipt.operational_status is authorization.operational_status
    assert receipt.epoch_reference == authorization.epoch_reference
    assert receipt.previous_operations_reference == authorization.previous_operations_reference
    assert receipt.previous_attestation_reference == authorization.previous_attestation_reference
    assert (
        receipt.previous_recovery_acceptance_reference
        == authorization.previous_recovery_acceptance_reference
    )
    assert (
        receipt.previous_recovery_receipt_reference
        == authorization.previous_recovery_receipt_reference
    )
    assert receipt.previous_recovery_reference == authorization.previous_recovery_reference
    assert (
        receipt.previous_recovery_authorization_reference
        == authorization.previous_recovery_authorization_reference
    )
    assert receipt.previous_recovery_action is authorization.previous_recovery_action
    assert receipt.adapter_reference == authorization.adapter_reference
    assert receipt.environment_reference == authorization.environment_reference
    assert receipt.artifact_reference == authorization.artifact_reference
    assert tuple(result.checkpoint for result in receipt.checkpoint_results) == (
        NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
    )


def test_failed_checkpoint_derives_failed_receipt() -> None:
    receipt = NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptService.record(
        recovery_authorization=_authorization(),
        receipt_reference="recovery-receipt:failed:62",
        recovery_reference="recovery-execution:failed:62",
        checkpoint_results=_checkpoint_results(
            failed_checkpoint=(
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint.TARGET_STATE_VERIFIED
            )
        ),
    )

    assert receipt.status is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.FAILED


def test_blank_receipt_or_recovery_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError,
        match="receipt_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptService.record(
            recovery_authorization=_authorization(),
            receipt_reference=" ",
            recovery_reference="recovery-execution:62",
            checkpoint_results=_checkpoint_results(),
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError,
        match="recovery_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptService.record(
            recovery_authorization=_authorization(),
            receipt_reference="recovery-receipt:62",
            recovery_reference=" ",
            checkpoint_results=_checkpoint_results(),
        )


def test_missing_or_duplicate_checkpoint_is_rejected() -> None:
    results = _checkpoint_results()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError,
        match="cover every required checkpoint",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptService.record(
            recovery_authorization=_authorization(),
            receipt_reference="recovery-receipt:missing:62",
            recovery_reference="recovery-execution:missing:62",
            checkpoint_results=results[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptService.record(
            recovery_authorization=_authorization(),
            receipt_reference="recovery-receipt:duplicate:62",
            recovery_reference="recovery-execution:duplicate:62",
            checkpoint_results=(*results, results[0]),
        )


def test_blank_checkpoint_evidence_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="evidence_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
            checkpoint=(
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpoint.AUTHORIZATION_ACKNOWLEDGED
            ),
            status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED,
            evidence_reference=" ",
        )


def test_reused_authorization_cycle_is_rejected_defensively() -> None:
    class _MalformedAuthorization(_RecoveryAuthorizationStub):
        authorization_reference = "recovery-auth:same:62"
        previous_recovery_authorization_reference = "recovery-auth:same:62"

    malformed = cast(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization,
        _MalformedAuthorization(),
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptError,
        match="distinct authorization cycle",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceiptService.record(
            recovery_authorization=malformed,
            receipt_reference="recovery-receipt:reused:62",
            recovery_reference="recovery-execution:reused:62",
            checkpoint_results=_checkpoint_results(),
        )


def test_direct_receipt_requires_canonical_results_and_matching_status() -> None:
    with pytest.raises(ValueError, match="canonicalized"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt(
            recovery_authorization=_authorization(),
            receipt_reference="recovery-receipt:direct:62",
            recovery_reference="recovery-execution:direct:62",
            status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED,
            checkpoint_results=_checkpoint_results(),
        )

    canonical_results = tuple(reversed(_checkpoint_results()))
    with pytest.raises(ValueError, match="status must match"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt(
            recovery_authorization=_authorization(),
            receipt_reference="recovery-receipt:status:62",
            recovery_reference="recovery-execution:status:62",
            status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.FAILED,
            checkpoint_results=canonical_results,
        )
