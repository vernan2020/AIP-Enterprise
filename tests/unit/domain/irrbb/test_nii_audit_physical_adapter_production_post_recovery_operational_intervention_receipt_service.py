from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_reattestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_post_recovery_operational_intervention_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService,
)


class _OperationalStatusReattestationStub:
    reattestation_reference = "status-reattestation:degraded:59"
    status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
    exception_references = ("incident:59",)
    epoch_reference = "steady-state:post-recovery:59"
    previous_operations_reference = "steady-state:pre-recovery:59"
    previous_attestation_reference = "status:pre-recovery:59"
    recovery_acceptance_reference = "recovery-acceptance:59"
    recovery_receipt_reference = "recovery-receipt:59"
    recovery_reference = "recovery-execution:59"
    recovery_authorization_reference = "recovery-auth:59"
    recovery_action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    intervention_authorization_reference = "intervention-auth:previous:59"
    intervention_action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _reattestation() -> NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation:
    return cast(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation,
        _OperationalStatusReattestationStub(),
    )


def _authorization(
    action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction = (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    ),
) -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization:
    evidence = tuple(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionEvidence(
            requirement=requirement,
            source_reference=f"post-recovery-intervention:{requirement.value.lower()}",
        )
        for requirement in NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionRequirement
    )
    return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization(
        operational_status_reattestation=_reattestation(),
        authorization_reference="intervention-auth:post-recovery:59",
        action=action,
        evidence=tuple(
            sorted(evidence, key=lambda item: (item.requirement.value, item.source_reference))
        ),
    )


def _checkpoint_results(
    *,
    non_success_checkpoint: (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint | None
    ) = None,
    non_success_status: (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus
    ) = NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.FAILED,
) -> tuple[NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult, ...]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult(
            checkpoint=checkpoint,
            status=(
                non_success_status
                if checkpoint is non_success_checkpoint
                else NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
            ),
            evidence_reference=f"observed:post-recovery:{checkpoint.value.lower()}",
        )
        for checkpoint in reversed(
            NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
        )
    )


def test_successful_receipt_preserves_exact_authorization_and_full_chain() -> None:
    authorization = _authorization()

    receipt = NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService.record(
        intervention_authorization=authorization,
        receipt_reference="intervention-receipt:post-recovery:59",
        intervention_reference="intervention-execution:post-recovery:59",
        checkpoint_results=_checkpoint_results(),
    )

    assert receipt.intervention_authorization is authorization
    assert (
        receipt.status
        is NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
    )
    assert receipt.authorization_reference == authorization.authorization_reference
    assert receipt.action is authorization.action
    assert receipt.reattestation_reference == authorization.reattestation_reference
    assert receipt.operational_status is authorization.status
    assert receipt.epoch_reference == authorization.epoch_reference
    assert receipt.previous_operations_reference == authorization.previous_operations_reference
    assert receipt.previous_attestation_reference == authorization.previous_attestation_reference
    assert receipt.recovery_acceptance_reference == authorization.recovery_acceptance_reference
    assert receipt.recovery_receipt_reference == authorization.recovery_receipt_reference
    assert receipt.recovery_reference == authorization.recovery_reference
    assert (
        receipt.recovery_authorization_reference == authorization.recovery_authorization_reference
    )
    assert receipt.recovery_action is authorization.recovery_action
    assert (
        receipt.previous_intervention_authorization_reference
        == authorization.previous_intervention_authorization_reference
    )
    assert receipt.previous_intervention_action is authorization.previous_intervention_action
    assert receipt.adapter_reference == authorization.adapter_reference
    assert receipt.environment_reference == authorization.environment_reference
    assert receipt.artifact_reference == authorization.artifact_reference
    assert tuple(item.checkpoint for item in receipt.checkpoint_results) == (
        NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
    )


@pytest.mark.parametrize(
    "checkpoint_status",
    [
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.FAILED,
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.NOT_EXECUTED,
    ],
)
def test_any_non_success_checkpoint_derives_failed_status(
    checkpoint_status: NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
) -> None:
    receipt = NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService.record(
        intervention_authorization=_authorization(
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.DEACTIVATE
        ),
        receipt_reference="intervention-receipt:post-recovery:failed:59",
        intervention_reference="intervention-execution:post-recovery:failed:59",
        checkpoint_results=_checkpoint_results(
            non_success_checkpoint=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.RESULTING_STATE_VERIFIED
            ),
            non_success_status=checkpoint_status,
        ),
    )

    assert (
        receipt.status is NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.FAILED
    )
    assert (
        receipt.action
        is NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.DEACTIVATE
    )


def test_missing_or_duplicate_checkpoint_result_fails_closed() -> None:
    authorization = _authorization()
    results = _checkpoint_results()

    with pytest.raises(ValueError, match="every required checkpoint"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService.record(
            intervention_authorization=authorization,
            receipt_reference="receipt:missing:59",
            intervention_reference="execution:missing:59",
            checkpoint_results=results[:-1],
        )

    with pytest.raises(ValueError, match="Duplicate"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService.record(
            intervention_authorization=authorization,
            receipt_reference="receipt:duplicate:59",
            intervention_reference="execution:duplicate:59",
            checkpoint_results=(*results, results[0]),
        )


def test_blank_receipt_intervention_or_evidence_reference_fails_closed() -> None:
    authorization = _authorization()
    results = _checkpoint_results()

    with pytest.raises(ValueError, match="receipt_reference"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService.record(
            intervention_authorization=authorization,
            receipt_reference=" ",
            intervention_reference="execution:59",
            checkpoint_results=results,
        )

    with pytest.raises(ValueError, match="intervention_reference"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService.record(
            intervention_authorization=authorization,
            receipt_reference="receipt:59",
            intervention_reference=" ",
            checkpoint_results=results,
        )

    with pytest.raises(ValueError, match="evidence_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult(
            checkpoint=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.AUTHORIZATION_ACKNOWLEDGED
            ),
            status=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
            ),
            evidence_reference=" ",
        )


def test_direct_receipt_rejects_inconsistent_status_and_noncanonical_results() -> None:
    authorization = _authorization()
    canonical_results = tuple(reversed(_checkpoint_results()))

    with pytest.raises(ValueError, match="status must match"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt(
            intervention_authorization=authorization,
            receipt_reference="receipt:invalid-status:59",
            intervention_reference="execution:invalid-status:59",
            status=NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.FAILED,
            checkpoint_results=canonical_results,
        )

    with pytest.raises(ValueError, match="canonicalized"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt(
            intervention_authorization=authorization,
            receipt_reference="receipt:noncanonical:59",
            intervention_reference="execution:noncanonical:59",
            status=NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED,
            checkpoint_results=_checkpoint_results(),
        )


def test_malformed_authorization_cycle_is_rejected_defensively() -> None:
    class _MalformedAuthorization:
        authorization_reference = "intervention-auth:same:59"
        previous_intervention_authorization_reference = "intervention-auth:same:59"
        reattestation_reference = "status-reattestation:degraded:59"
        status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED

    malformed = cast(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization,
        _MalformedAuthorization(),
    )

    with pytest.raises(ValueError, match="distinct authorization cycle"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService.record(
            intervention_authorization=malformed,
            receipt_reference="receipt:malformed:59",
            intervention_reference="execution:malformed:59",
            checkpoint_results=_checkpoint_results(),
        )
