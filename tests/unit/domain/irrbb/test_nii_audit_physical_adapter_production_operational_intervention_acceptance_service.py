from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement,
)
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
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_intervention_acceptance_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceService,
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


def _authorization() -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorization:
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
        action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
        evidence=tuple(
            sorted(evidence, key=lambda item: (item.requirement.value, item.source_reference))
        ),
    )


def _checkpoint_results(
    *,
    failed_checkpoint: (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint | None
    ) = None,
) -> tuple[
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointResult, ...
]:
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


def _successful_receipt() -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceipt:
    return NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService.record(
        intervention_authorization=_authorization(),
        receipt_reference="intervention-receipt:2026-09-12",
        intervention_reference="intervention-execution:42",
        checkpoint_results=_checkpoint_results(),
    )


def _failed_receipt() -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceipt:
    return NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceiptService.record(
        intervention_authorization=_authorization(),
        receipt_reference="intervention-receipt:failed",
        intervention_reference="intervention-execution:failed",
        checkpoint_results=_checkpoint_results(
            failed_checkpoint=(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpoint.RESULTING_STATE_VERIFIED
            )
        ),
    )


def _acceptance_evidence() -> tuple[
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence, ...
]:
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence(
            requirement=requirement,
            source_reference=f"acceptance:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(
                NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceRequirement
            )
        )
    )


def test_acceptance_preserves_exact_receipt_and_derives_identity() -> None:
    receipt = _successful_receipt()

    acceptance = (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceService.accept(
            intervention_receipt=receipt,
            acceptance_reference="intervention-acceptance:2026-09-13",
            evidence=_acceptance_evidence(),
        )
    )

    assert acceptance.intervention_receipt is receipt
    assert acceptance.intervention_receipt_reference == receipt.receipt_reference
    assert acceptance.intervention_reference == receipt.intervention_reference
    assert acceptance.authorization_reference == receipt.authorization_reference
    assert acceptance.action is receipt.action
    assert acceptance.attestation_reference == receipt.attestation_reference
    assert acceptance.operations_reference == receipt.operations_reference
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
        receipt.status
        is NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.FAILED
    )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError,
        match="successful receipt",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceService.accept(
            intervention_receipt=receipt,
            acceptance_reference="intervention-acceptance:failed",
            evidence=_acceptance_evidence(),
        )


def test_blank_acceptance_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError,
        match="acceptance_reference",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceService.accept(
            intervention_receipt=_successful_receipt(),
            acceptance_reference=" ",
            evidence=_acceptance_evidence(),
        )


def test_missing_acceptance_requirement_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError,
        match="cover every required acceptance",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceService.accept(
            intervention_receipt=_successful_receipt(),
            acceptance_reference="intervention-acceptance:missing",
            evidence=_acceptance_evidence()[:-1],
        )


def test_duplicate_acceptance_requirement_is_rejected() -> None:
    evidence = _acceptance_evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceService.accept(
            intervention_receipt=_successful_receipt(),
            acceptance_reference="intervention-acceptance:duplicate",
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
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance(
            intervention_receipt=_successful_receipt(),
            acceptance_reference="intervention-acceptance:direct",
            evidence=_acceptance_evidence(),
        )
