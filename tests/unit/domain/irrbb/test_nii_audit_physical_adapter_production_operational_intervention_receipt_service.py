from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceipt,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_intervention_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService,
)


class _StatusAttestationStub:
    status = NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
    attestation_reference = "status:degraded"
    operations_reference = "steady-state:2026-09-12"
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _status_attestation() -> NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation:
    return cast(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation,
        _StatusAttestationStub(),
    )


def _authorization(
    action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction = (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    ),
) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization:
    evidence = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence(
            requirement=requirement,
            source_reference=f"intervention:{requirement.value.lower()}",
        )
        for requirement in NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement
    )
    return NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization(
        operational_status_attestation=_status_attestation(),
        authorization_reference="intervention-auth:2026-09-12",
        action=action,
        evidence=tuple(
            sorted(evidence, key=lambda item: (item.requirement.value, item.source_reference))
        ),
    )


def _checkpoint_results(
    *,
    failed_checkpoint: NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint
    | None = None,
) -> tuple[NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult, ...]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult(
            checkpoint=checkpoint,
            status=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.FAILED
                if checkpoint is failed_checkpoint
                else NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
            ),
            evidence_reference=f"observed:{checkpoint.value.lower()}",
        )
        for checkpoint in reversed(
            NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
        )
    )


def test_successful_intervention_receipt_preserves_exact_authorization_and_canonicalizes() -> None:
    authorization = _authorization()

    receipt = NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService.record(
        intervention_authorization=authorization,
        receipt_reference="intervention-receipt:2026-09-12",
        intervention_reference="intervention-execution:42",
        checkpoint_results=_checkpoint_results(),
    )

    assert receipt.intervention_authorization is authorization
    assert receipt.status is NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
    assert receipt.authorization_reference == authorization.authorization_reference
    assert receipt.action is authorization.action
    assert receipt.attestation_reference == authorization.attestation_reference
    assert receipt.adapter_reference == authorization.adapter_reference
    assert receipt.environment_reference == authorization.environment_reference
    assert receipt.artifact_reference == authorization.artifact_reference
    assert tuple(item.checkpoint for item in receipt.checkpoint_results) == (
        NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_CHECKPOINT_ORDER
    )


@pytest.mark.parametrize(
    "action",
    [
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.DEACTIVATE,
    ],
)
def test_failed_checkpoint_derives_failed_status_without_action_inference(
    action: NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
) -> None:
    authorization = _authorization(action)

    receipt = NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService.record(
        intervention_authorization=authorization,
        receipt_reference="intervention-receipt:failed",
        intervention_reference="intervention-execution:failed",
        checkpoint_results=_checkpoint_results(
            failed_checkpoint=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.RESULTING_STATE_VERIFIED
            )
        ),
    )

    assert receipt.action is action
    assert receipt.status is NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.FAILED


def test_missing_or_duplicate_checkpoint_result_fails_closed() -> None:
    authorization = _authorization()
    results = _checkpoint_results()

    with pytest.raises(ValueError, match="every required checkpoint"):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService.record(
            intervention_authorization=authorization,
            receipt_reference="receipt:missing",
            intervention_reference="execution:missing",
            checkpoint_results=results[:-1],
        )

    with pytest.raises(ValueError, match="Duplicate"):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService.record(
            intervention_authorization=authorization,
            receipt_reference="receipt:duplicate",
            intervention_reference="execution:duplicate",
            checkpoint_results=(*results, results[0]),
        )


def test_blank_receipt_or_intervention_reference_fails_closed() -> None:
    authorization = _authorization()
    results = _checkpoint_results()

    with pytest.raises(ValueError, match="receipt_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService.record(
            intervention_authorization=authorization,
            receipt_reference=" ",
            intervention_reference="execution:42",
            checkpoint_results=results,
        )

    with pytest.raises(ValueError, match="intervention_reference"):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService.record(
            intervention_authorization=authorization,
            receipt_reference="receipt:42",
            intervention_reference=" ",
            checkpoint_results=results,
        )


def test_direct_receipt_rejects_status_that_does_not_match_results() -> None:
    authorization = _authorization()
    canonical_results = tuple(reversed(_checkpoint_results()))

    with pytest.raises(ValueError, match="status must match"):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceipt(
            intervention_authorization=authorization,
            receipt_reference="receipt:invalid-status",
            intervention_reference="execution:invalid-status",
            status=NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.FAILED,
            checkpoint_results=canonical_results,
        )
