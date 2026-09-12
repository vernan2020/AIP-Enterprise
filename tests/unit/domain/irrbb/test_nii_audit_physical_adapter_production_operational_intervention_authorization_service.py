from __future__ import annotations

from typing import cast

import pytest

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_authorization import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_status_attestation import (
    NIIRunAuditPhysicalAdapterProductionOperationalStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusEvidence,
    NIIRunAuditPhysicalAdapterProductionOperationalStatusRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_steady_state_operations import (
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperations,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_operational_intervention_authorization_service import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationService,
)


class _SteadyStateOperationsStub:
    operations_reference = "steady-state:2026-09-12"
    runtime_activation_acceptance_reference = "runtime-acceptance:2026-09-12"
    adapter_reference = "adapter-v1"
    environment_reference = "production-cr-primary"
    artifact_reference = "artifact:nii-audit-adapter-v1"


def _operations() -> NIIRunAuditPhysicalAdapterProductionSteadyStateOperations:
    return cast(
        NIIRunAuditPhysicalAdapterProductionSteadyStateOperations,
        _SteadyStateOperationsStub(),
    )


def _status_attestation(
    status: NIIRunAuditPhysicalAdapterProductionOperationalStatus,
) -> NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation:
    evidence = tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalStatusEvidence(
            requirement=requirement,
            source_reference=f"status:{requirement.value.lower()}",
        )
        for requirement in NIIRunAuditPhysicalAdapterProductionOperationalStatusRequirement
    )
    return NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation(
        steady_state_operations=_operations(),
        attestation_reference=f"status:{status.value.lower()}",
        status=status,
        evidence=tuple(
            sorted(evidence, key=lambda item: (item.requirement.value, item.source_reference))
        ),
        exception_references=(
            ()
            if status is NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY
            else ("incident:42",)
        ),
    )


def _intervention_evidence() -> (
    tuple[NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence, ...]
):
    return tuple(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionEvidence(
            requirement=requirement,
            source_reference=f"intervention:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement)
        )
    )


@pytest.mark.parametrize(
    "status",
    [
        NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED,
        NIIRunAuditPhysicalAdapterProductionOperationalStatus.UNAVAILABLE,
    ],
)
def test_nonhealthy_status_can_authorize_explicit_action_without_inference(
    status: NIIRunAuditPhysicalAdapterProductionOperationalStatus,
) -> None:
    attestation = _status_attestation(status)

    authorization = (
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationService.authorize(
            operational_status_attestation=attestation,
            authorization_reference="intervention-auth:2026-09-12",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=_intervention_evidence(),
        )
    )

    assert authorization.operational_status_attestation is attestation
    assert authorization.status is status
    assert (
        authorization.action
        is NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND
    )
    assert authorization.attestation_reference == attestation.attestation_reference
    assert authorization.adapter_reference == attestation.adapter_reference
    assert tuple(item.requirement.value for item in authorization.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionOperationalInterventionRequirement
        )
    )


def test_healthy_status_cannot_authorize_intervention() -> None:
    attestation = _status_attestation(NIIRunAuditPhysicalAdapterProductionOperationalStatus.HEALTHY)

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError,
        match="HEALTHY",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationService.authorize(
            operational_status_attestation=attestation,
            authorization_reference="intervention-auth:healthy",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.DEACTIVATE,
            evidence=_intervention_evidence(),
        )


def test_missing_or_duplicate_intervention_evidence_fails_closed() -> None:
    attestation = _status_attestation(
        NIIRunAuditPhysicalAdapterProductionOperationalStatus.DEGRADED
    )
    evidence = _intervention_evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError,
        match="every required control",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationService.authorize(
            operational_status_attestation=attestation,
            authorization_reference="intervention-auth:missing",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=evidence[:-1],
        )

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationService.authorize(
            operational_status_attestation=attestation,
            authorization_reference="intervention-auth:duplicate",
            action=NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction.SUSPEND,
            evidence=(*evidence, evidence[0]),
        )
