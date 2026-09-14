from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_acceptance import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_steady_state_operations import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_STEADY_STATE_OPERATIONS_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperations,
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsError,
    NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsEvidence,
)


class NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsService:
    """Record governance evidence for one accepted runtime entering steady-state operations."""

    @classmethod
    def record(
        cls,
        *,
        activation_acceptance: NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance,
        operations_reference: str,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsEvidence],
    ) -> NIIRunAuditPhysicalAdapterProductionSteadyStateOperations:
        if not operations_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsError(
                "NII audit physical adapter production steady-state operations_reference is required"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsError(
                    "Duplicate NII audit physical adapter production steady-state operations "
                    "evidence requirement"
                )
            evidence_by_requirement[item.requirement] = item

        missing_requirements = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_STEADY_STATE_OPERATIONS_REQUIREMENTS
            - set(evidence_by_requirement)
        )
        unexpected_requirements = set(evidence_by_requirement) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_STEADY_STATE_OPERATIONS_REQUIREMENTS
        )
        if missing_requirements or unexpected_requirements:
            raise NIIRunAuditPhysicalAdapterProductionSteadyStateOperationsError(
                "NII audit physical adapter production steady-state operations evidence "
                "must cover every required operations control"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionSteadyStateOperations(
            activation_acceptance=activation_acceptance,
            operations_reference=operations_reference,
            evidence=canonical_evidence,
        )
