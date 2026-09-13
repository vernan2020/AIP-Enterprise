from __future__ import annotations

import pytest

from aip.domain.irrbb.nii_audit_persistence_activation import (
    NIIRunAuditPersistenceActivationAuthorization,
    NIIRunAuditPersistenceActivationConfiguration,
)
from aip.domain.irrbb.nii_audit_persistence_readiness import (
    REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
    NIIAuditPersistenceEvidence,
    NIIAuditPersistenceReadinessAssessment,
    NIIAuditPersistenceReadinessStatus,
    NIIAuditPersistenceRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_certification import (
    NIIRunAuditPhysicalAdapterCertificationBundle,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_execution_authorization import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_execution_receipt import (
    NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus,
    NIIRunAuditPhysicalAdapterProductionDeploymentStepResult,
    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_plan import (
    NIIRunAuditPhysicalAdapterProductionDeploymentStep,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_execution_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceEvidence,
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_promotion import (
    NIIRunAuditPhysicalAdapterProductionPromotionEvidence,
    NIIRunAuditPhysicalAdapterProductionPromotionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_readiness import (
    NIIRunAuditPhysicalAdapterProductionEvidence,
    NIIRunAuditPhysicalAdapterProductionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_acceptance import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceEvidence,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_authorization import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationEvidence,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus,
)
from aip.domain.irrbb.nii_audit_physical_persistence import (
    NIIRunAuditActivatedPhysicalPersistence,
    NIIRunAuditPhysicalPersistenceDescriptor,
)
from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaVersion,
)
from aip.domain.irrbb.nii_audit_serialization_compatibility import (
    NIIAuditReadableSchemaCompatibility,
    NIIRunAuditSerializationCompatibilityCertificate,
)
from aip.domain.irrbb.nii_run_audit import NIIRunAuditRepositoryPutResult
from aip.domain.irrbb.services.nii_audit_physical_adapter_certification_service import (
    NIIRunAuditPhysicalAdapterCertificationService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_deployment_execution_authorization_service import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_deployment_execution_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_deployment_plan_service import (
    NIIRunAuditPhysicalAdapterProductionDeploymentPlanService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_post_execution_acceptance_service import (
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_promotion_service import (
    NIIRunAuditPhysicalAdapterProductionPromotionService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_readiness_service import (
    NIIRunAuditPhysicalAdapterProductionReadinessService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_runtime_activation_acceptance_service import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_runtime_activation_authorization_service import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorizationService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_runtime_activation_receipt_service import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService,
)


class _Repository:
    def get_by_run_reference(self, *, run_reference: str):
        return None

    def put_if_absent(self, *, record):
        return NIIRunAuditRepositoryPutResult(created=True, record=record)


def _schema_contract() -> NIIAuditSchemaEvolutionContract:
    version = NIIAuditSchemaVersion(schema_reference="nii-audit", version=1)
    return NIIAuditSchemaEvolutionContract(
        current_version=version,
        readable_versions=frozenset({version}),
        migration_steps=(),
        source_reference="schema-policy",
    )


def _certification_bundle() -> NIIRunAuditPhysicalAdapterCertificationBundle:
    schema_contract = _schema_contract()
    readiness = NIIAuditPersistenceReadinessAssessment(
        adapter_reference="adapter-v1",
        status=NIIAuditPersistenceReadinessStatus.READY,
        certified_requirements=REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
        missing_requirements=frozenset(),
        evidence=(
            NIIAuditPersistenceEvidence(
                requirement=NIIAuditPersistenceRequirement.ATOMIC_PUT_IF_ABSENT,
                source_reference="repo-conformance-report",
            ),
        ),
    )
    compatibility = NIIRunAuditSerializationCompatibilityCertificate(
        schema_contract=schema_contract,
        codec_reference="codec-v1",
        integrity_reference="integrity-v1",
        readable_schema_compatibility=(
            NIIAuditReadableSchemaCompatibility(
                source_version=schema_contract.current_version,
                migration_steps=(),
                transformer_references=(),
            ),
        ),
    )
    configuration = NIIRunAuditPersistenceActivationConfiguration(
        adapter_reference="adapter-v1",
        schema_contract=schema_contract,
        codec_reference="codec-v1",
        integrity_reference="integrity-v1",
        source_reference="activation-policy",
    )
    activation = NIIRunAuditPersistenceActivationAuthorization(
        configuration=configuration,
        readiness=readiness,
        compatibility=compatibility,
    )
    activated = NIIRunAuditActivatedPhysicalPersistence(
        authorization=activation,
        descriptor=NIIRunAuditPhysicalPersistenceDescriptor(
            adapter_reference="adapter-v1",
            schema_contract=schema_contract,
            codec_reference="codec-v1",
            integrity_reference="integrity-v1",
        ),
        repository=_Repository(),
    )
    return NIIRunAuditPhysicalAdapterCertificationService.certify(
        certification_reference="physical-adapter-cert-v1",
        activated_persistence=activated,
        evidence_references=("activation-policy", "repo-conformance-report"),
    )


def _promotion_authorization():
    readiness = NIIRunAuditPhysicalAdapterProductionReadinessService.assess(
        certification_bundle=_certification_bundle(),
        environment_reference="production-cr-primary",
        evidence=tuple(
            NIIRunAuditPhysicalAdapterProductionEvidence(
                requirement=requirement,
                source_reference=f"readiness:{requirement.value.lower()}",
            )
            for requirement in NIIRunAuditPhysicalAdapterProductionRequirement
        ),
    )
    return NIIRunAuditPhysicalAdapterProductionPromotionService.authorize(
        readiness_assessment=readiness,
        authorization_reference="promotion-auth-2026-09-11",
        evidence=tuple(
            NIIRunAuditPhysicalAdapterProductionPromotionEvidence(
                requirement=requirement,
                source_reference=f"promotion:{requirement.value.lower()}",
            )
            for requirement in NIIRunAuditPhysicalAdapterProductionPromotionRequirement
        ),
    )


def _deployment_plan():
    return NIIRunAuditPhysicalAdapterProductionDeploymentPlanService.build(
        promotion_authorization=_promotion_authorization(),
        plan_reference="deployment-plan-2026-09-11",
        release_reference="release:nii-audit-v1",
        change_reference="change:chg-2026-0911",
        artifact_reference="artifact:nii-audit-adapter-v1",
        rollback_reference="runbook:nii-audit-rollback-v1",
        steps=(
            NIIRunAuditPhysicalAdapterProductionDeploymentStep(
                sequence=2,
                instruction_reference="runbook:post-deployment-validation",
            ),
            NIIRunAuditPhysicalAdapterProductionDeploymentStep(
                sequence=1,
                instruction_reference="runbook:deploy-authorized-artifact",
            ),
        ),
    )


def _execution_authorization():
    return NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService.authorize(
        deployment_plan=_deployment_plan(),
        execution_authorization_reference="execution-auth-2026-09-11",
        evidence=tuple(
            NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence(
                requirement=requirement,
                source_reference=f"execution:{requirement.value.lower()}",
            )
            for requirement in NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement
        ),
    )


def _successful_execution_receipt():
    return NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(
        execution_authorization=_execution_authorization(),
        receipt_reference="receipt:deployment-2026-09-11",
        execution_reference="executor-run:001",
        step_results=(
            NIIRunAuditPhysicalAdapterProductionDeploymentStepResult(
                sequence=2,
                status=NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
                evidence_reference="executor:step-2:succeeded",
            ),
            NIIRunAuditPhysicalAdapterProductionDeploymentStepResult(
                sequence=1,
                status=NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
                evidence_reference="executor:step-1:succeeded",
            ),
        ),
        rollback_status=NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED,
        rollback_evidence_reference="executor:rollback-not-required",
    )


def _post_execution_acceptance():
    return NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceService.accept(
        execution_receipt=_successful_execution_receipt(),
        acceptance_reference="post-execution-acceptance:001",
        evidence=tuple(
            NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceEvidence(
                requirement=requirement,
                source_reference=f"acceptance:{requirement.value.lower()}",
            )
            for requirement in NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceRequirement
        ),
    )


def _runtime_activation_authorization():
    return NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorizationService.authorize(
        post_execution_acceptance=_post_execution_acceptance(),
        activation_authorization_reference="runtime-activation-auth:001",
        evidence=tuple(
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationEvidence(
                requirement=requirement,
                source_reference=f"runtime-activation:{requirement.value.lower()}",
            )
            for requirement in NIIRunAuditPhysicalAdapterProductionRuntimeActivationRequirement
        ),
    )


def _checkpoint_result(
    checkpoint: NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint,
    status: NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus,
) -> NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointResult:
    return NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointResult(
        checkpoint=checkpoint,
        status=status,
        evidence_reference=f"runtime-executor:{checkpoint.value.lower()}:{status.value.lower()}",
    )


def _successful_activation_receipt():
    return NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService.record(
        activation_authorization=_runtime_activation_authorization(),
        receipt_reference="runtime-activation-receipt:001",
        activation_reference="runtime-executor-run:001",
        checkpoint_results=tuple(
            _checkpoint_result(
                checkpoint,
                NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.SUCCEEDED,
            )
            for checkpoint in reversed(
                NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER
            )
        ),
    )


def _failed_activation_receipt():
    statuses = {
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.DEPENDENCY_WIRING_APPLIED: NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.SUCCEEDED,
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.ADAPTER_REGISTRATION_CONFIRMED: NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.FAILED,
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.STARTUP_SEQUENCE_COMPLETED: NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.NOT_EXECUTED,
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.RUNTIME_HEALTH_CONFIRMED: NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.NOT_EXECUTED,
    }
    return NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService.record(
        activation_authorization=_runtime_activation_authorization(),
        receipt_reference="runtime-activation-receipt:failed",
        activation_reference="runtime-executor-run:failed",
        checkpoint_results=tuple(
            _checkpoint_result(checkpoint, statuses[checkpoint])
            for checkpoint in NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER
        ),
    )


def _acceptance_evidence():
    return tuple(
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceEvidence(
            requirement=requirement,
            source_reference=f"runtime-acceptance:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceRequirement)
        )
    )


def test_acceptance_preserves_exact_receipt_and_derives_identity() -> None:
    receipt = _successful_activation_receipt()

    acceptance = NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceService.accept(
        activation_receipt=receipt,
        acceptance_reference="runtime-activation-acceptance:001",
        evidence=_acceptance_evidence(),
    )

    assert acceptance.activation_receipt is receipt
    assert acceptance.runtime_activation_receipt_reference == "runtime-activation-receipt:001"
    assert acceptance.activation_reference == "runtime-executor-run:001"
    assert acceptance.activation_authorization_reference == "runtime-activation-auth:001"
    assert acceptance.post_execution_acceptance_reference == "post-execution-acceptance:001"
    assert acceptance.deployment_receipt_reference == "receipt:deployment-2026-09-11"
    assert acceptance.deployment_execution_reference == "executor-run:001"
    assert acceptance.deployment_execution_authorization_reference == "execution-auth-2026-09-11"
    assert acceptance.plan_reference == "deployment-plan-2026-09-11"
    assert acceptance.adapter_reference == "adapter-v1"
    assert acceptance.environment_reference == "production-cr-primary"
    assert acceptance.artifact_reference == "artifact:nii-audit-adapter-v1"
    assert acceptance.planned_rollback_reference == "runbook:nii-audit-rollback-v1"
    assert tuple(item.requirement.value for item in acceptance.evidence) == tuple(
        sorted(
            requirement.value
            for requirement in NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceRequirement
        )
    )


def test_failed_activation_receipt_is_rejected() -> None:
    receipt = _failed_activation_receipt()
    assert receipt.status is NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.FAILED

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError,
        match="successful activation receipt",
    ):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceService.accept(
            activation_receipt=receipt,
            acceptance_reference="runtime-activation-acceptance:failed",
            evidence=_acceptance_evidence(),
        )


def test_missing_acceptance_requirement_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError,
        match="cover every required acceptance",
    ):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceService.accept(
            activation_receipt=_successful_activation_receipt(),
            acceptance_reference="runtime-activation-acceptance:missing",
            evidence=_acceptance_evidence()[:-1],
        )


def test_duplicate_acceptance_requirement_is_rejected() -> None:
    evidence = _acceptance_evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceService.accept(
            activation_receipt=_successful_activation_receipt(),
            acceptance_reference="runtime-activation-acceptance:duplicate",
            evidence=(*evidence, evidence[0]),
        )


def test_blank_acceptance_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError,
        match="acceptance_reference is required",
    ):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceService.accept(
            activation_receipt=_successful_activation_receipt(),
            acceptance_reference=" ",
            evidence=_acceptance_evidence(),
        )


def test_blank_acceptance_evidence_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_reference is required"):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceEvidence(
            requirement=(
                NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceRequirement.RUNTIME_STABILITY_VALIDATED
            ),
            source_reference=" ",
        )


def test_direct_acceptance_requires_canonical_evidence_order() -> None:
    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance(
            activation_receipt=_successful_activation_receipt(),
            acceptance_reference="runtime-activation-acceptance:direct",
            evidence=_acceptance_evidence(),
        )
