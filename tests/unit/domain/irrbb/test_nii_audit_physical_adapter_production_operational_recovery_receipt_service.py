from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_recovery_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError,
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_recovery_authorization_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_recovery_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService,
)


class _InterventionAcceptanceStub:
    acceptance_reference = "intervention-acceptance:54"
    intervention_receipt_reference = "intervention-receipt:54"
    intervention_reference = "intervention-execution:54"
    authorization_reference = "intervention-auth:54"
    action = NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    attestation_reference = "status:degraded"
    operations_reference = "steady-state:54"
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _intervention_acceptance() -> (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance
):
    return cast(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance,
        _InterventionAcceptanceStub(),
    )


def _recovery_authorization():
    evidence = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryEvidence(
            requirement=requirement,
            source_reference=f"recovery-auth:{requirement.value.lower()}",
        )
        for requirement in NIIRunAuditPhysicalAdapterProductionOperationalRecoveryRequirement
    )
    return NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorizationService.authorize(
        intervention_acceptance=_intervention_acceptance(),
        authorization_reference="recovery-auth:54",
        action=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME,
        evidence=evidence,
    )


def _checkpoint_results(
    *,
    failed_index: int | None = None,
    not_executed_index: int | None = None,
):
    results = []
    for index, checkpoint in enumerate(
        NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
    ):
        status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED
        if index == failed_index:
            status = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.FAILED
        if index == not_executed_index:
            status = (
                NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.NOT_EXECUTED
            )
        results.append(
            NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
                checkpoint=checkpoint,
                status=status,
                evidence_reference=f"observed:{checkpoint.value.lower()}",
            )
        )
    return tuple(reversed(results))


def test_successful_receipt_preserves_exact_authorization_and_chain_identity() -> None:
    authorization = _recovery_authorization()

    receipt = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService.record(
        recovery_authorization=authorization,
        receipt_reference="recovery-receipt:54",
        recovery_reference="recovery-execution:54",
        checkpoint_results=_checkpoint_results(),
    )

    assert receipt.recovery_authorization is authorization
    assert receipt.status is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED
    assert receipt.action is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAction.RESUME
    assert receipt.authorization_reference == authorization.authorization_reference
    assert (
        receipt.intervention_acceptance_reference == authorization.intervention_acceptance_reference
    )
    assert receipt.intervention_receipt_reference == authorization.intervention_receipt_reference
    assert (
        receipt.intervention_action
        is NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )
    assert receipt.adapter_reference == authorization.adapter_reference
    assert tuple(item.checkpoint for item in receipt.checkpoint_results) == (
        NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER
    )


@pytest.mark.parametrize(
    ("failed_index", "not_executed_index"),
    [(1, None), (None, 2)],
)
def test_non_successful_checkpoint_derives_failed_receipt(
    failed_index: int | None,
    not_executed_index: int | None,
) -> None:
    receipt = NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService.record(
        recovery_authorization=_recovery_authorization(),
        receipt_reference="recovery-receipt:failed",
        recovery_reference="recovery-execution:failed",
        checkpoint_results=_checkpoint_results(
            failed_index=failed_index,
            not_executed_index=not_executed_index,
        ),
    )

    assert receipt.status is NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.FAILED


def test_duplicate_or_missing_checkpoint_is_rejected() -> None:
    results = _checkpoint_results()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService.record(
            recovery_authorization=_recovery_authorization(),
            receipt_reference="recovery-receipt:duplicate",
            recovery_reference="recovery-execution:duplicate",
            checkpoint_results=(*results, results[0]),
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError,
        match="cover every required checkpoint",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService.record(
            recovery_authorization=_recovery_authorization(),
            receipt_reference="recovery-receipt:missing",
            recovery_reference="recovery-execution:missing",
            checkpoint_results=results[:-1],
        )


def test_blank_receipt_or_recovery_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError,
        match="receipt_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService.record(
            recovery_authorization=_recovery_authorization(),
            receipt_reference=" ",
            recovery_reference="recovery-execution:54",
            checkpoint_results=_checkpoint_results(),
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptError,
        match="recovery_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService.record(
            recovery_authorization=_recovery_authorization(),
            receipt_reference="recovery-receipt:54",
            recovery_reference=" ",
            checkpoint_results=_checkpoint_results(),
        )


def test_blank_checkpoint_evidence_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="evidence_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointResult(
            checkpoint=(
                NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_RECOVERY_CHECKPOINT_ORDER[0]
            ),
            status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryCheckpointStatus.SUCCEEDED,
            evidence_reference=" ",
        )


def test_direct_receipt_rejects_noncanonical_order_and_inconsistent_status() -> None:
    canonical_results = tuple(reversed(_checkpoint_results()))

    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt(
            recovery_authorization=_recovery_authorization(),
            receipt_reference="recovery-receipt:direct-order",
            recovery_reference="recovery-execution:direct-order",
            status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.SUCCEEDED,
            checkpoint_results=tuple(reversed(canonical_results)),
        )

    with pytest.raises(ValueError, match="status must match checkpoint results"):
        NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt(
            recovery_authorization=_recovery_authorization(),
            receipt_reference="recovery-receipt:direct-status",
            recovery_reference="recovery-execution:direct-status",
            status=NIIRunAuditPhysicalAdapterProductionOperationalRecoveryStatus.FAILED,
            checkpoint_results=canonical_results,
        )
