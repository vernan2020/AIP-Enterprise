from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement,
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
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance,
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_recovery_operational_recovery_receipt import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_post_recovery_operational_recovery_acceptance_service import (
    NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceService,
)


class _ReceiptStub:
    receipt_reference = "recovery-receipt:post-recovery:63"
    recovery_reference = "recovery-execution:post-recovery:63"
    authorization_reference = "recovery-auth:post-recovery:63"
    previous_recovery_authorization_reference = "recovery-auth:previous:63"
    action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    intervention_acceptance_reference = "intervention-acceptance:post-recovery:63"
    intervention_receipt_reference = "intervention-receipt:post-recovery:63"
    intervention_reference = "intervention-execution:post-recovery:63"
    intervention_authorization_reference = "intervention-auth:post-recovery:63"
    intervention_action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    reattestation_reference = "status-reattestation:63"
    operational_status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
    epoch_reference = "steady-state:post-recovery:63"
    previous_operations_reference = "steady-state:pre-recovery:63"
    previous_attestation_reference = "status:pre-recovery:63"
    previous_recovery_acceptance_reference = "recovery-acceptance:previous:63"
    previous_recovery_receipt_reference = "recovery-receipt:previous:63"
    previous_recovery_reference = "recovery-execution:previous:63"
    previous_recovery_action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    previous_intervention_authorization_reference = "intervention-auth:previous:63"
    previous_intervention_action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"
    status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
    checkpoint_results = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
            checkpoint=checkpoint,
            status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED,
            evidence_reference=f"observed:{checkpoint.value.lower()}",
        )
        for checkpoint in NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
    )


def _receipt() -> NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt:
    return cast(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
        _ReceiptStub(),
    )


def _evidence() -> tuple[
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence, ...
]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence(
            requirement=requirement,
            source_reference=f"post-recovery-acceptance:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement)
        )
    )


def test_acceptance_preserves_exact_receipt_and_full_chain() -> None:
    receipt = _receipt()
    acceptance = (
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=receipt,
            acceptance_reference="recovery-acceptance:post-recovery:63",
            evidence=_evidence(),
        )
    )

    assert acceptance.recovery_receipt is receipt
    assert acceptance.recovery_receipt_reference == receipt.receipt_reference
    assert acceptance.recovery_reference == receipt.recovery_reference
    assert acceptance.recovery_authorization_reference == receipt.authorization_reference
    assert acceptance.recovery_action is receipt.action
    assert acceptance.intervention_acceptance_reference == receipt.intervention_acceptance_reference
    assert acceptance.intervention_authorization_reference == receipt.intervention_authorization_reference
    assert acceptance.reattestation_reference == receipt.reattestation_reference
    assert acceptance.epoch_reference == receipt.epoch_reference
    assert (
        acceptance.previous_recovery_authorization_reference
        == receipt.previous_recovery_authorization_reference
    )
    assert acceptance.adapter_reference == receipt.adapter_reference
    assert acceptance.environment_reference == receipt.environment_reference
    assert acceptance.artifact_reference == receipt.artifact_reference
    assert tuple(item.requirement.value for item in acceptance.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement
        )
    )


def test_failed_receipt_is_rejected() -> None:
    class _FailedReceipt(_ReceiptStub):
        status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.FAILED

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError,
        match="successful receipt",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=cast(
                NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
                _FailedReceipt(),
            ),
            acceptance_reference="recovery-acceptance:failed:63",
            evidence=_evidence(),
        )


def test_success_status_with_failed_checkpoint_is_rejected_defensively() -> None:
    failed_result = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
        checkpoint=NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER[0],
        status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.FAILED,
        evidence_reference="observed:failed",
    )

    class _MalformedReceipt(_ReceiptStub):
        checkpoint_results = (
            failed_result,
            *_ReceiptStub.checkpoint_results[1:],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError,
        match="every checkpoint to succeed",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=cast(
                NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
                _MalformedReceipt(),
            ),
            acceptance_reference="recovery-acceptance:malformed:63",
            evidence=_evidence(),
        )


def test_reused_recovery_authorization_cycle_is_rejected() -> None:
    class _ReusedCycleReceipt(_ReceiptStub):
        previous_recovery_authorization_reference = _ReceiptStub.authorization_reference

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError,
        match="distinct recovery cycle",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=cast(
                NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryReceipt,
                _ReusedCycleReceipt(),
            ),
            acceptance_reference="recovery-acceptance:reused:63",
            evidence=_evidence(),
        )


def test_blank_acceptance_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError,
        match="acceptance_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=_receipt(),
            acceptance_reference=" ",
            evidence=_evidence(),
        )


def test_missing_or_duplicate_requirement_is_rejected() -> None:
    evidence = _evidence()
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError,
        match="cover every required acceptance",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=_receipt(),
            acceptance_reference="recovery-acceptance:missing:63",
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=_receipt(),
            acceptance_reference="recovery-acceptance:duplicate:63",
            evidence=(*evidence, evidence[0]),
        )


def test_direct_acceptance_requires_canonical_evidence() -> None:
    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAcceptance(
            recovery_receipt=_receipt(),
            acceptance_reference="recovery-acceptance:direct:63",
            evidence=_evidence(),
        )
