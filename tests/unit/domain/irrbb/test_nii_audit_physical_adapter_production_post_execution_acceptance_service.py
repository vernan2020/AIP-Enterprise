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
    NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus,
    NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus,
    NIIRunAuditPhysicalAdapterProductionDeploymentStepResult,
    NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_plan import (
    NIIRunAuditPhysicalAdapterProductionDeploymentStep,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_post_execution_acceptance import (
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance,
    NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError,
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


def _step_result(
    sequence: int,
    status: NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus,
) -> NIIRunAuditPhysicalAdapterProductionDeploymentStepResult:
    return NIIRunAuditPhysicalAdapterProductionDeploymentStepResult(
        sequence=sequence,
        status=status,
        evidence_reference=f"executor:step-{sequence}:{status.value.lower()}",
    )


def _successful_execution_receipt():
    return NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(
        execution_authorization=_execution_authorization(),
        receipt_reference="receipt:deployment-2026-09-11",
        execution_reference="executor-run:001",
        step_results=(
            _step_result(
                2,
                NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
            ),
            _step_result(
                1,
                NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.SUCCEEDED,
            ),
        ),
        rollback_status=NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED,
        rollback_evidence_reference="executor:rollback-not-required",
    )


def _failed_execution_receipt():
    return NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(
        execution_authorization=_execution_authorization(),
        receipt_reference="receipt:deployment-2026-09-11-failed",
        execution_reference="executor-run:002",
        step_results=(
            _step_result(
                1,
                NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.FAILED,
            ),
            _step_result(
                2,
                NIIRunAuditPhysicalAdapterProductionDeploymentStepStatus.NOT_EXECUTED,
            ),
        ),
        rollback_status=NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.SUCCEEDED,
        rollback_evidence_reference="executor:rollback:002",
    )


def _acceptance_evidence():
    return tuple(
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceEvidence(
            requirement=requirement,
            source_reference=f"acceptance:{requirement.value.lower()}",
        )
        for requirement in reversed(
            tuple(NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceRequirement)
        )
    )


def test_acceptance_preserves_exact_receipt_and_derives_identity() -> None:
    receipt = _successful_execution_receipt()

    acceptance = NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceService.accept(
        execution_receipt=receipt,
        acceptance_reference="post-execution-acceptance:001",
        evidence=_acceptance_evidence(),
    )

    assert acceptance.execution_receipt is receipt
    assert acceptance.receipt_reference == "receipt:deployment-2026-09-11"
    assert acceptance.execution_reference == "executor-run:001"
    assert acceptance.execution_authorization_reference == "execution-auth-2026-09-11"
    assert acceptance.plan_reference == "deployment-plan-2026-09-11"
    assert acceptance.adapter_reference == "adapter-v1"
    assert acceptance.environment_reference == "production-cr-primary"
    assert acceptance.artifact_reference == "artifact:nii-audit-adapter-v1"
    assert acceptance.planned_rollback_reference == "runbook:nii-audit-rollback-v1"
    assert tuple(item.requirement.value for item in acceptance.evidence) == tuple(
        sorted(requirement.value for requirement in NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceRequirement)
    )


def test_failed_execution_receipt_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError,
        match="successful execution receipt",
    ):
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceService.accept(
            execution_receipt=_failed_execution_receipt(),
            acceptance_reference="post-execution-acceptance:failed",
            evidence=_acceptance_evidence(),
        )


def test_missing_acceptance_requirement_is_rejected() -> None:
    evidence = _acceptance_evidence()[:-1]

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError,
        match="cover every required acceptance",
    ):
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceService.accept(
            execution_receipt=_successful_execution_receipt(),
            acceptance_reference="post-execution-acceptance:missing",
            evidence=evidence,
        )


def test_duplicate_acceptance_requirement_is_rejected() -> None:
    evidence = _acceptance_evidence()

    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError,
        match="Duplicate",
    ):
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceService.accept(
            execution_receipt=_successful_execution_receipt(),
            acceptance_reference="post-execution-acceptance:duplicate",
            evidence=(*evidence, evidence[0]),
        )


def test_blank_acceptance_reference_is_rejected() -> None:
    with pytest.raises(
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceError,
        match="acceptance_reference is required",
    ):
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptanceService.accept(
            execution_receipt=_successful_execution_receipt(),
            acceptance_reference=" ",
            evidence=_acceptance_evidence(),
        )


def test_direct_acceptance_requires_canonical_evidence_order() -> None:
    with pytest.raises(ValueError, match="must be canonicalized"):
        NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance(
            execution_receipt=_successful_execution_receipt(),
            acceptance_reference="post-execution-acceptance:direct",
            evidence=_acceptance_evidence(),
        )


def test_successful_receipt_precondition_is_explicit() -> None:
    receipt = _successful_execution_receipt()

    assert receipt.status is NIIRunAuditPhysicalAdapterProductionDeploymentExecutionStatus.SUCCEEDED
    assert (
        receipt.rollback_status
        is NIIRunAuditPhysicalAdapterProductionDeploymentRollbackStatus.NOT_REQUIRED
    )
