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
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError,
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus,
    NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus,
    NIIRunAuditPhysicalAdapterProductionDeploymentStepResult,
    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_plan import (
    NIIRunAuditPhysicalAdapterProductionDeploymentStep,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_promotion import (
    NIIRunAuditPhysicalAdapterProductionPromotionEvidence,
    NIIRunAuditPhysicalAdapterProductionPromotionRequirement,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_readiness import (
    NIIRunAuditPhysicalAdapterProductionEvidence,
    NIIRunAuditPhysicalAdapterProductionRequirement,
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
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_promotion_service import (
    NIIRunAuditPhysicalAdapterProductionPromotionService,
)
from aip.domain.irrbb.services.nii_audit_physical_adapter_production_readiness_service import (
    NIIRunAuditPhysicalAdapterProductionReadinessService,
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
    plan = _deployment_plan()
    return NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService.authorize(
        deployment_plan=plan,
        execution_authorization_reference="execution-auth-2026-09-11",
        evidence=tuple(
            NIIRunAuditPhysicalAdapterProductionDeploymentExecutionEvidence(
                requirement=requirement,
                source_reference=f"execution:{requirement.value.lower()}",
            )
            for requirement in NIIRunAuditPhysicalAdapterProductionDeploymentExecutionRequirement
        ),
    )


def _step_result(
    sequence: int,
    status: NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus,
) -> NIIRunAuditPhysicalAdapterProductionDeploymentStepResult:
    return NIIRunAuditPhysicalAdapterProductionDeploymentStepResult(
        sequence=sequence,
        status=status,
        evidence_reference=f"executor:step-{sequence}:{status.value.lower()}",
    )


def test_successful_execution_receipt_preserves_exact_authorization() -> None:
    authorization = _execution_authorization()

    receipt = NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(
        execution_authorization=authorization,
        receipt_reference="receipt:deployment-2026-09-11",
        execution_reference="executor-run:001",
        step_results=(
            _step_result(2, NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED),
            _step_result(1, NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED),
        ),
        rollback_status=NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED,
        rollback_evidence_reference="executor:rollback-not-required",
    )

    assert receipt.execution_authorization is authorization
    assert receipt.status is NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.SUCCEEDED
    assert tuple(result.sequence for result in receipt.step_results) == (1, 2)
    assert receipt.execution_authorization_reference == "execution-auth-2026-09-11"
    assert receipt.plan_reference == "deployment-plan-2026-09-11"
    assert receipt.adapter_reference == "adapter-v1"
    assert receipt.environment_reference == "production-cr-primary"
    assert receipt.artifact_reference == "artifact:nii-audit-adapter-v1"
    assert receipt.planned_rollback_reference == "runbook:nii-audit-rollback-v1"


def test_failed_execution_derives_failed_status_and_records_rollback() -> None:
    receipt = NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(
        execution_authorization=_execution_authorization(),
        receipt_reference="receipt:deployment-2026-09-11-failed",
        execution_reference="executor-run:002",
        step_results=(
            _step_result(1, NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.FAILED),
            _step_result(2, NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.NOT_EXECUTED),
        ),
        rollback_status=NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.SUCCEEDED,
        rollback_evidence_reference="executor:rollback:002",
    )

    assert receipt.status is NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.FAILED
    assert (
        receipt.rollback_status
        is NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.SUCCEEDED
    )
    assert tuple(result.status for result in receipt.step_results) == (
        NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.FAILED,
        NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.NOT_EXECUTED,
    )


def test_missing_plan_step_result_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError,
        match="missing=2",
    ):
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(
            execution_authorization=_execution_authorization(),
            receipt_reference="receipt:missing-step",
            execution_reference="executor-run:003",
            step_results=(
                _step_result(
                    1,
                    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
                ),
            ),
            rollback_status=NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED,
            rollback_evidence_reference="executor:rollback-not-required",
        )


def test_duplicate_step_result_sequence_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError,
        match="Duplicate.*sequence 1",
    ):
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(
            execution_authorization=_execution_authorization(),
            receipt_reference="receipt:duplicate-step",
            execution_reference="executor-run:004",
            step_results=(
                _step_result(
                    1,
                    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
                ),
                _step_result(
                    1,
                    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.FAILED,
                ),
            ),
            rollback_status=NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED,
            rollback_evidence_reference="executor:rollback-not-required",
        )


def test_successful_execution_cannot_report_rollback_attempt() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError,
        match="cannot require rollback",
    ):
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(
            execution_authorization=_execution_authorization(),
            receipt_reference="receipt:invalid-rollback",
            execution_reference="executor-run:005",
            step_results=(
                _step_result(
                    1,
                    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
                ),
                _step_result(
                    2,
                    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
                ),
            ),
            rollback_status=NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.SUCCEEDED,
            rollback_evidence_reference="executor:rollback:005",
        )


@pytest.mark.parametrize(
    ("receipt_reference", "execution_reference", "rollback_evidence_reference"),
    (
        (" ", "executor-run:006", "executor:rollback-not-required"),
        ("receipt:blank-execution", " ", "executor:rollback-not-required"),
        ("receipt:blank-rollback", "executor-run:007", " "),
    ),
)
def test_blank_receipt_references_are_rejected(
    receipt_reference: str,
    execution_reference: str,
    rollback_evidence_reference: str,
) -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptError,
        match="is required",
    ):
        NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(
            execution_authorization=_execution_authorization(),
            receipt_reference=receipt_reference,
            execution_reference=execution_reference,
            step_results=(
                _step_result(
                    1,
                    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
                ),
                _step_result(
                    2,
                    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
                ),
            ),
            rollback_status=NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED,
            rollback_evidence_reference=rollback_evidence_reference,
        )
