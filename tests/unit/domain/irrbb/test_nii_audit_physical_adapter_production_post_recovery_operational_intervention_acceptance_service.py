from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement,
)
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
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_post_recovery_operational_intervention_acceptance_service import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_post_recovery_operational_intervention_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService,
)


class _PostRecoveryInterventionAuthorizationStub:
    authorization_reference = "intervention-auth:post-recovery:60"
    action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    reattestation_reference = "status-reattestation:degraded:60"
    status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
    epoch_reference = "steady-state:post-recovery:60"
    previous_operations_reference = "steady-state:pre-recovery:60"
    previous_attestation_reference = "status:pre-recovery:60"
    recovery_acceptance_reference = "recovery-acceptance:60"
    recovery_receipt_reference = "recovery-receipt:60"
    recovery_reference = "recovery-execution:60"
    recovery_authorization_reference = "recovery-auth:60"
    recovery_action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    previous_intervention_authorization_reference = "intervention-auth:previous:60"
    previous_intervention_action = (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _authorization() -> (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization
):
    return cast(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization,
        _PostRecoveryInterventionAuthorizationStub(),
    )


def _checkpoint_results(
    *,
    failed_checkpoint: (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint | None
    ) = None,
) -> tuple[NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult, ...]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult(
            checkpoint=checkpoint,
            status=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.FAILED
                if checkpoint is failed_checkpoint
                else NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
            ),
            evidence_reference=f"observed:post-recovery:{checkpoint.value.lower()}",
        )
        for checkpoint in reversed(
            NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
        )
    )


def _successful_receipt() -> (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt
):
    return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService.record(
        intervention_authorization=_authorization(),
        receipt_reference="intervention-receipt:post-recovery:60",
        intervention_reference="intervention-execution:post-recovery:60",
        checkpoint_results=_checkpoint_results(),
    )


def _failed_receipt() -> (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt
):
    return NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceiptService.record(
        intervention_authorization=_authorization(),
        receipt_reference="intervention-receipt:post-recovery:failed:60",
        intervention_reference="intervention-execution:post-recovery:failed:60",
        checkpoint_results=_checkpoint_results(
            failed_checkpoint=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.RESULTING_STATE_VERIFIED
            )
        ),
    )


def _acceptance_evidence() -> (
    tuple[NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence, ...]
):
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence(
            requirement=requirement,
            source_reference=f"post-recovery-acceptance:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement)
        )
    )


def test_acceptance_preserves_exact_receipt_and_full_chain() -> None:
    receipt = _successful_receipt()

    acceptance = NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceService.accept(
        intervention_receipt=receipt,
        acceptance_reference="intervention-acceptance:post-recovery:60",
        evidence=_acceptance_evidence(),
    )

    assert acceptance.intervention_receipt is receipt
    assert acceptance.intervention_receipt_reference == receipt.receipt_reference
    assert acceptance.intervention_reference == receipt.intervention_reference
    assert acceptance.authorization_reference == receipt.authorization_reference
    assert acceptance.action is receipt.action
    assert acceptance.reattestation_reference == receipt.reattestation_reference
    assert acceptance.operational_status is receipt.operational_status
    assert acceptance.epoch_reference == receipt.epoch_reference
    assert acceptance.previous_operations_reference == receipt.previous_operations_reference
    assert acceptance.previous_attestation_reference == receipt.previous_attestation_reference
    assert acceptance.recovery_acceptance_reference == receipt.recovery_acceptance_reference
    assert acceptance.recovery_receipt_reference == receipt.recovery_receipt_reference
    assert acceptance.recovery_reference == receipt.recovery_reference
    assert acceptance.recovery_authorization_reference == receipt.recovery_authorization_reference
    assert acceptance.recovery_action is receipt.recovery_action
    assert (
        acceptance.previous_intervention_authorization_reference
        == receipt.previous_intervention_authorization_reference
    )
    assert acceptance.previous_intervention_action is receipt.previous_intervention_action
    assert acceptance.adapter_reference == receipt.adapter_reference
    assert acceptance.environment_reference == receipt.environment_reference
    assert acceptance.artifact_reference == receipt.artifact_reference
    assert tuple(item.requirement.value for item in acceptance.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement
        )
    )


def test_failed_intervention_receipt_is_rejected() -> None:
    receipt = _failed_receipt()
    assert (
        receipt.status is NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.FAILED
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError,
        match="successful receipt",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceService.accept(
            intervention_receipt=receipt,
            acceptance_reference="intervention-acceptance:post-recovery:failed:60",
            evidence=_acceptance_evidence(),
        )


def test_success_status_with_non_success_checkpoint_is_rejected_defensively() -> None:
    failed_result = NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult(
        checkpoint=(
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.RESULTING_STATE_VERIFIED
        ),
        status=NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.FAILED,
        evidence_reference="observed:malformed:resulting-state",
    )

    class _MalformedReceipt:
        status = NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
        checkpoint_results = (failed_result,)
        authorization_reference = "intervention-auth:post-recovery:60"
        previous_intervention_authorization_reference = "intervention-auth:previous:60"

    malformed = cast(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt,
        _MalformedReceipt(),
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError,
        match="every checkpoint to succeed",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceService.accept(
            intervention_receipt=malformed,
            acceptance_reference="intervention-acceptance:malformed:60",
            evidence=_acceptance_evidence(),
        )


def test_reused_authorization_cycle_is_rejected_defensively() -> None:
    class _MalformedReceipt:
        status = NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
        checkpoint_results = tuple(reversed(_checkpoint_results()))
        authorization_reference = "intervention-auth:same:60"
        previous_intervention_authorization_reference = "intervention-auth:same:60"

    malformed = cast(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionReceipt,
        _MalformedReceipt(),
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError,
        match="distinct authorization cycle",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceService.accept(
            intervention_receipt=malformed,
            acceptance_reference="intervention-acceptance:reused:60",
            evidence=_acceptance_evidence(),
        )


def test_blank_acceptance_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError,
        match="acceptance_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceService.accept(
            intervention_receipt=_successful_receipt(),
            acceptance_reference=" ",
            evidence=_acceptance_evidence(),
        )


def test_missing_or_duplicate_acceptance_requirement_is_rejected() -> None:
    evidence = _acceptance_evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError,
        match="cover every required acceptance",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceService.accept(
            intervention_receipt=_successful_receipt(),
            acceptance_reference="intervention-acceptance:missing:60",
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptanceService.accept(
            intervention_receipt=_successful_receipt(),
            acceptance_reference="intervention-acceptance:duplicate:60",
            evidence=(*evidence, evidence[0]),
        )


def test_blank_evidence_source_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence(
            requirement=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement.INTERVENTION_RECEIPT_VERIFIED
            ),
            source_reference=" ",
        )


def test_direct_acceptance_requires_canonical_evidence() -> None:
    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance(
            intervention_receipt=_successful_receipt(),
            acceptance_reference="intervention-acceptance:direct:60",
            evidence=_acceptance_evidence(),
        )
