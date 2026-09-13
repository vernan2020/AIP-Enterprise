from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_acceptance import (
    REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence,
)
from aip.domain.irrbb.nii_audit_physical_adapter_production_operational_intervention_receipt import (
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceipt,
    NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus,
)


class NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceService:
    """Accept one exact successful externally observed operational intervention."""

    @classmethod
    def accept(
        cls,
        *,
        intervention_receipt: NIIRunAuditPhysicalAdapterProductionOperationalInterventionReceipt,
        acceptance_reference: str,
        evidence: Iterable[
            NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceEvidence
        ],
    ) -> NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance:
        if (
            intervention_receipt.status
            is not NIIRunAuditPhysicalAdapterProductionOperationalInterventionStatus.SUCCEEDED
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError(
                "NII audit operational intervention acceptance requires a successful receipt"
            )
        if not all(
            result.status
            is NIIRunAuditPhysicalAdapterProductionOperationalInterventionCheckpointStatus.SUCCEEDED
            for result in intervention_receipt.checkpoint_results
        ):
            raise NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError(
                "NII audit operational intervention acceptance requires every checkpoint to succeed"
            )
        if not acceptance_reference.strip():
            raise NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError(
                "NII audit operational intervention acceptance_reference is required"
            )

        evidence_items = tuple(evidence)
        by_requirement = {}
        for item in evidence_items:
            if item.requirement in by_requirement:
                raise NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError(
                    "Duplicate NII audit operational intervention acceptance evidence requirement"
                )
            by_requirement[item.requirement] = item

        missing = (
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS
            - set(by_requirement)
        )
        unexpected = set(by_requirement) - set(
            REQUIRED_NII_AUDIT_PHYSICAL_ADAPTER_PRODUCTION_OPERATIONAL_INTERVENTION_ACCEPTANCE_REQUIREMENTS
        )
        if missing or unexpected:
            raise NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptanceError(
                "NII audit operational intervention acceptance evidence must cover every required acceptance"
            )

        canonical_evidence = tuple(
            sorted(
                evidence_items,
                key=lambda item: (item.requirement.value, item.source_reference),
            )
        )
        return NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance(
            intervention_receipt=intervention_receipt,
            acceptance_reference=acceptance_reference,
            evidence=canonical_evidence,
        )
