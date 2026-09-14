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
from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_authorization import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationEvidence,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_receipt import (
    NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointResult,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError,
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


def _successful_checkpoint_results():
    return tuple(
        _checkpoint_result(
            checkpoint,
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.SUCCEEDED,
        )
        for checkpoint in reversed(
            NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER
        )
    )


def test_successful_receipt_preserves_exact_authorization_and_derives_identity() -> None:
    authorization = _runtime_activation_authorization()

    receipt = NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService.record(
        activation_authorization=authorization,
        receipt_reference="runtime-activation-receipt:001",
        activation_reference="runtime-executor-run:001",
        checkpoint_results=_successful_checkpoint_results(),
    )

    assert receipt.activation_authorization is authorization
    assert receipt.status is NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.SUCCEEDED
    assert receipt.activation_authorization_reference == "runtime-activation-auth:001"
    assert receipt.acceptance_reference == "post-execution-acceptance:001"
    assert receipt.deployment_receipt_reference == "receipt:deployment-2026-09-11"
    assert receipt.deployment_execution_reference == "executor-run:001"
    assert receipt.deployment_execution_authorization_reference == "execution-auth-2026-09-11"
    assert receipt.plan_reference == "deployment-plan-2026-09-11"
    assert receipt.adapter_reference == "adapter-v1"
    assert receipt.environment_reference == "production-cr-primary"
    assert receipt.artifact_reference == "artifact:nii-audit-adapter-v1"
    assert receipt.planned_rollback_reference == "runbook:nii-audit-rollback-v1"
    assert tuple(item.checkpoint for item in receipt.checkpoint_results) == (
        NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER
    )


def test_failed_checkpoint_derives_failed_activation_status() -> None:
    results = (
        _checkpoint_result(
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.DEPENDENCY_WIRING_APPLIED,
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.SUCCEEDED,
        ),
        _checkpoint_result(
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.ADAPTER_REGISTRATION_CONFIRMED,
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.FAILED,
        ),
        _checkpoint_result(
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.STARTUP_SEQUENCE_COMPLETED,
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.NOT_EXECUTED,
        ),
        _checkpoint_result(
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpoint.RUNTIME_HEALTH_CONFIRMED,
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.NOT_EXECUTED,
        ),
    )

    receipt = NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService.record(
        activation_authorization=_runtime_activation_authorization(),
        receipt_reference="runtime-activation-receipt:failed",
        activation_reference="runtime-executor-run:failed",
        checkpoint_results=results,
    )

    assert receipt.status is NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.FAILED


def test_missing_checkpoint_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError,
        match="cover every required checkpoint",
    ):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService.record(
            activation_authorization=_runtime_activation_authorization(),
            receipt_reference="runtime-activation-receipt:missing",
            activation_reference="runtime-executor-run:missing",
            checkpoint_results=_successful_checkpoint_results()[:-1],
        )


def test_duplicate_checkpoint_is_rejected() -> None:
    results = _successful_checkpoint_results()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService.record(
            activation_authorization=_runtime_activation_authorization(),
            receipt_reference="runtime-activation-receipt:duplicate",
            activation_reference="runtime-executor-run:duplicate",
            checkpoint_results=(*results, results[0]),
        )


@pytest.mark.parametrize(
    ("receipt_reference", "activation_reference", "message"),
    (
        (" ", "runtime-executor-run:001", "receipt_reference is required"),
        ("runtime-activation-receipt:001", " ", "activation_reference is required"),
    ),
)
def test_blank_receipt_references_are_rejected(
    receipt_reference: str,
    activation_reference: str,
    message: str,
) -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptError,
        match=message,
    ):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService.record(
            activation_authorization=_runtime_activation_authorization(),
            receipt_reference=receipt_reference,
            activation_reference=activation_reference,
            checkpoint_results=_successful_checkpoint_results(),
        )


def test_direct_receipt_requires_canonical_checkpoint_order() -> None:
    authorization = _runtime_activation_authorization()

    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt(
            activation_authorization=authorization,
            receipt_reference="runtime-activation-receipt:direct",
            activation_reference="runtime-executor-run:direct",
            status=NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.SUCCEEDED,
            checkpoint_results=_successful_checkpoint_results(),
        )


def test_direct_receipt_rejects_inconsistent_global_status() -> None:
    authorization = _runtime_activation_authorization()
    canonical_results = tuple(
        _checkpoint_result(
            checkpoint,
            NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.SUCCEEDED,
        )
        for checkpoint in NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_CHECKPOINT_ORDER
    )

    with pytest.raises(ValueError, match="status must match checkpoint results"):
        NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt(
            activation_authorization=authorization,
            receipt_reference="runtime-activation-receipt:status-mismatch",
            activation_reference="runtime-executor-run:status-mismatch",
            status=NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.FAILED,
            checkpoint_results=canonical_results,
        )
