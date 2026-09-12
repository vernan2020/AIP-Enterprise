from __future__ import annotations

from collections.abc import Iterable

from aip.domain.irrbb.nii_audit_physical_adapter_certification import (
    NIIRunAuditPhysicalAdapterCertificationBundle,
    NIIRunAuditPhysicalAdapterCertificationError,
)
from aip.domain.irrbb.nii_audit_physical_persistence import (
    NIIRunAuditActivatedPhysicalPersistence,
)


class NIIRunAuditPhysicalAdapterCertificationService:
    """Certify one activated physical adapter as a complete auditable bundle."""

    @classmethod
    def certify(
        cls,
        *,
        certification_reference: str,
        activated_persistence: NIIRunAuditActivatedPhysicalPersistence,
        evidence_references: Iterable[str],
    ) -> NIIRunAuditPhysicalAdapterCertificationBundle:
        if not certification_reference.strip():
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification_reference is required"
            )

        references = tuple(evidence_references)
        if not references:
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification evidence is required"
            )
        if any(not reference.strip() for reference in references):
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification evidence reference is required"
            )
        if len(references) != len(set(references)):
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "Duplicate NII audit physical adapter certification evidence reference"
            )

        authorization = activated_persistence.authorization
        readiness = authorization.readiness
        descriptor = activated_persistence.descriptor
        configuration = authorization.configuration
        compatibility = authorization.compatibility

        if not readiness.is_ready:
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification requires READY assessment"
            )
        if readiness.adapter_reference != descriptor.adapter_reference:
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification readiness identity mismatch"
            )
        if configuration.adapter_reference != descriptor.adapter_reference:
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification adapter identity mismatch"
            )
        if compatibility.schema_contract != descriptor.schema_contract:
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification schema contract mismatch"
            )
        if compatibility.codec_reference != descriptor.codec_reference:
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification codec identity mismatch"
            )
        if compatibility.integrity_reference != descriptor.integrity_reference:
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification integrity identity mismatch"
            )

        required_evidence = {
            configuration.source_reference,
            *(item.source_reference for item in readiness.evidence),
        }
        missing_evidence = required_evidence.difference(references)
        if missing_evidence:
            raise NIIRunAuditPhysicalAdapterCertificationError(
                "NII audit physical adapter certification is missing prerequisite evidence: "
                + ", ".join(sorted(missing_evidence))
            )

        return NIIRunAuditPhysicalAdapterCertificationBundle(
            certification_reference=certification_reference,
            activated_persistence=activated_persistence,
            evidence_references=tuple(sorted(references)),
        )
