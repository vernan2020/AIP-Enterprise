from __future__ import annotations

import hashlib
from dataclasses import dataclass

NII_REPRODUCIBILITY_SCHEMA_VERSION = "aip.irrbb.nii-run-reproducibility.v1"


@dataclass(frozen=True, slots=True)
class NIIRunEvidenceManifest:
    """Auditable evidence manifest for one NII methodology run specification.

    ``run_reference`` identifies the execution. ``specification_fingerprint``
    identifies the methodological perimeter and therefore deliberately excludes
    the execution-specific run reference.
    """

    run_reference: str
    schema_version: str
    specification_fingerprint: str
    canonical_payload: str
    policy_references: tuple[str, ...]
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.run_reference.strip():
            raise ValueError("NII reproducibility run_reference is required")
        if not self.schema_version.strip():
            raise ValueError("NII reproducibility schema_version is required")
        if not self.canonical_payload:
            raise ValueError("NII reproducibility canonical_payload is required")
        if not self.policy_references:
            raise ValueError("NII reproducibility policy references are required")
        if not self.evidence_references:
            raise ValueError("NII reproducibility evidence references are required")
        if tuple(sorted(self.policy_references)) != self.policy_references:
            raise ValueError("NII reproducibility policy references must be canonicalized")
        if tuple(sorted(self.evidence_references)) != self.evidence_references:
            raise ValueError("NII reproducibility evidence references must be canonicalized")

        expected = hashlib.sha256(self.canonical_payload.encode("utf-8")).hexdigest()
        if self.specification_fingerprint != expected:
            raise ValueError("NII reproducibility fingerprint does not match canonical payload")
