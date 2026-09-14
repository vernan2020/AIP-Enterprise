from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_deployment_plan import (
    NIIRunAuditPhysicalAdapterProductionDeploymentPlan,
    NIIRunAuditPhysicalAdapterProductionDeploymentPlanError,
    NIIRunAuditPhysicalAdapterProductionDeploymentStep,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_promotion import (
    NIIRunAuditPhysicalAdapterProductionPromotionAuthorization,
)


class NIIRunAuditPhysicalAdapterProductionDeploymentPlanService:
    """Build a deterministic, non-executable deployment plan from Phase 40 authorization."""

    @classmethod
    def build(
        cls,
        *,
        promotion_authorization: NIIRunAuditPhysicalAdapterProductionPromotionAuthorization,
        plan_reference: str,
        release_reference: str,
        change_reference: str,
        artifact_reference: str,
        rollback_reference: str,
        steps: Iterable[NIIRunAuditPhysicalAdapterProductionDeploymentStep],
    ) -> NIIRunAuditPhysicalAdapterProductionDeploymentPlan:
        required_references = {
            "plan_reference": plan_reference,
            "release_reference": release_reference,
            "change_reference": change_reference,
            "artifact_reference": artifact_reference,
            "rollback_reference": rollback_reference,
        }
        for name, value in required_references.items():
            if not value.strip():
                raise NIIRunAuditPhysicalAdapterProductionDeploymentPlanError(
                    f"NII audit physical adapter production deployment {name} is required"
                )

        step_items = tuple(steps)
        if not step_items:
            raise NIIRunAuditPhysicalAdapterProductionDeploymentPlanError(
                "NII audit physical adapter production deployment plan requires at least one step"
            )

        sequences = tuple(step.sequence for step in step_items)
        if len(sequences) != len(set(sequences)):
            raise NIIRunAuditPhysicalAdapterProductionDeploymentPlanError(
                "Duplicate NII audit physical adapter production deployment step sequence"
            )

        instruction_references = tuple(step.instruction_reference for step in step_items)
        if len(instruction_references) != len(set(instruction_references)):
            raise NIIRunAuditPhysicalAdapterProductionDeploymentPlanError(
                "Duplicate NII audit physical adapter production deployment instruction_reference"
            )

        canonical_steps = tuple(sorted(step_items, key=lambda step: step.sequence))
        expected_sequences = tuple(range(1, len(canonical_steps) + 1))
        actual_sequences = tuple(step.sequence for step in canonical_steps)
        if actual_sequences != expected_sequences:
            raise NIIRunAuditPhysicalAdapterProductionDeploymentPlanError(
                "NII audit physical adapter production deployment steps must be contiguous from 1"
            )

        return NIIRunAuditPhysicalAdapterProductionDeploymentPlan(
            promotion_authorization=promotion_authorization,
            plan_reference=plan_reference,
            release_reference=release_reference,
            change_reference=change_reference,
            artifact_reference=artifact_reference,
            rollback_reference=rollback_reference,
            steps=canonical_steps,
        )
