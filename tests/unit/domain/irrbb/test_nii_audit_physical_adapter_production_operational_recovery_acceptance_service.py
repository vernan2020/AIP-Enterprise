from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_recovery_acceptance_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_recovery_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService,
)


class _RecoveryAuthorizationStub:
    authorization_reference = "recovery-auth:55"
    action = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    intervention_acceptance_reference = "intervention-acceptance:55"
    intervention_receipt_reference = "intervention-receipt:55"
    intervention_reference = "intervention-execution:55"
    intervention_authorization_reference = "intervention-auth:55"
    intervention_action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    attestation_reference = "status:degraded"
    operations_reference = "steady-state:55"
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _recovery_authorization() -> NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization:
    return cast(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization,
        _RecoveryAuthorizationStub(),
    )


def _receipt(*, failed_index: int | None = None):
    results = []
    for index, checkpoint in enumerate(
        NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
    ):
        status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
        if index == failed_index:
            status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.FAILED
        results.append(
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
                checkpoint=checkpoint,
                status=status,
                evidence_reference=f"observed:{checkpoint.value.lower()}",
            )
        )
    return NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService.record(
        recovery_authorization=_recovery_authorization(),
        receipt_reference="recovery-receipt:55",
        recovery_reference="recovery-execution:55",
        checkpoint_results=results,
    )


def _acceptance_evidence():
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence(
            requirement=requirement,
            source_reference=f"acceptance:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement)
        )
    )


def test_valid_acceptance_preserves_exact_receipt_and_chain_identity() -> None:
    receipt = _receipt()

    acceptance = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceService.accept(
        recovery_receipt=receipt,
        acceptance_reference="recovery-acceptance:55",
        evidence=_acceptance_evidence(),
    )

    assert acceptance.recovery_receipt is receipt
    assert acceptance.recovery_receipt_reference == receipt.receipt_reference
    assert acceptance.recovery_reference == receipt.recovery_reference
    assert acceptance.recovery_authorization_reference == receipt.authorization_reference
    assert acceptance.recovery_action is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    assert acceptance.intervention_acceptance_reference == receipt.intervention_acceptance_reference
    assert acceptance.intervention_receipt_reference == receipt.intervention_receipt_reference
    assert (
        acceptance.intervention_action
        is NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )
    assert acceptance.adapter_reference == receipt.adapter_reference
    assert acceptance.environment_reference == receipt.environment_reference
    assert acceptance.artifact_reference == receipt.artifact_reference


def test_failed_recovery_receipt_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError,
        match="successful receipt",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=_receipt(failed_index=1),
            acceptance_reference="recovery-acceptance:failed",
            evidence=_acceptance_evidence(),
        )


def test_blank_acceptance_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError,
        match="acceptance_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=_receipt(),
            acceptance_reference=" ",
            evidence=_acceptance_evidence(),
        )


def test_missing_or_duplicate_acceptance_requirement_is_rejected() -> None:
    receipt = _receipt()
    evidence = _acceptance_evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError,
        match="cover every required acceptance",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=receipt,
            acceptance_reference="recovery-acceptance:missing",
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceService.accept(
            recovery_receipt=receipt,
            acceptance_reference="recovery-acceptance:duplicate",
            evidence=(*evidence, evidence[0]),
        )


def test_blank_evidence_source_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceEvidence(
            requirement=(
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptanceRequirement.RECOVERY_RECEIPT_VERIFIED
            ),
            source_reference=" ",
        )


def test_direct_acceptance_requires_successful_checkpoints_and_canonical_evidence() -> None:
    receipt = _receipt()

    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance(
            recovery_receipt=receipt,
            acceptance_reference="recovery-acceptance:direct",
            evidence=_acceptance_evidence(),
        )

    successful_results = list(receipt.checkpoint_results)
    successful_results[0] = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
        checkpoint=successful_results[0].checkpoint,
        status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.FAILED,
        evidence_reference="tampered:failed",
    )
    tampered_receipt = cast(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt,
        object.__new__(NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt),
    )
    object.__setattr__(tampered_receipt, "recovery_authorization", receipt.recovery_authorization)
    object.__setattr__(tampered_receipt, "receipt_reference", receipt.receipt_reference)
    object.__setattr__(tampered_receipt, "recovery_reference", receipt.recovery_reference)
    object.__setattr__(
        tampered_receipt,
        "status",
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED,
    )
    object.__setattr__(tampered_receipt, "checkpoint_results", tuple(successful_results))

    canonical_evidence = tuple(
        sorted(
            _acceptance_evidence(),
            key=lambda item: (item.requirement.value, item.source_reference),
        )
    )
    with pytest.raises(ValueError, match="every checkpoint"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAcceptance(
            recovery_receipt=tampered_receipt,
            acceptance_reference="recovery-acceptance:tampered",
            evidence=canonical_evidence,
        )
