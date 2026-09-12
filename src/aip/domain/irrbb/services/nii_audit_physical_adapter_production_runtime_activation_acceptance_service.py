from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_acceptance import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_ACCEPTANCE_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_runtime_activation_receipt import (
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt,
    NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus,
)


class NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceService:
    """Accept one exact successful runtime activation receipt."""

    @classmethod
    def accept(
        cls,
        *,
        activation_receipt: NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt,
        acceptance_reference: str,
        evidence: Iterable[NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceEvidence],
    ) -> NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance:
        if (
            activation_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionRuntimeActivationStatus.SUCCEEDED
        ):
            raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError(
                "NII audit physical adapter production runtime activation acceptance requires "
                "a successful activation receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionRuntimeActivationCheckpointStatus.SUCCEEDED
            for result in activation_receipt.checkpoint_results
        ):
            raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError(
                "NII audit physical adapter production runtime activation acceptance requires "
                "every activation checkpoint to succeed"
            )
        if not acceptance_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError(
                "NII audit physical adapter production runtime activation "
                "acceptance_reference is required"
            )

        evidence_items = tuple(evidence)
        evidence_by_requirement = {}
        for item in evidence_items:
            if item.requirement in evidence_by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError(
                    "Duplicate NII audit physical adapter production runtime activation "
                    "acceptance evidence requirement"
                )
            evidence_by_requirement[item.requirement] = item

        missing_requirements = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_ACCEPTANCE_REQUIREMENTS
            - set(evidence_by_requirement)
        )
        unexpected_requirements = set(evidence_by_requirement) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_RUNTIME_ACTIVATION_ACCEPTANCE_REQUIREMENTS
        )
        if missing_requirements or unexpected_requirements:
            raise NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceError(
                "NII audit physical adapter production runtime activation acceptance evidence "
                "must cover every required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance(
            activation_receipt=activation_receipt,
            acceptance_reference=acceptance_reference,
            evidence=canonical_evidence,
        )
