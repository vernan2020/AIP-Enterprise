from __future__ import annotations

import json
from hashlib import sha256

from aip.domain.irrbb.nii_reproducibility import (
    NII_REPRODUCIBILITY_SCHEMA_VERSION,
    NIIRunEvidenceManifest,
)
from aip.domain.irrbb.nii_run_specification import NIIMethodologyRunSpecification


class NIIRunReproducibilityService:
    """Build a deterministic evidence manifest for an NII run specification."""

    @classmethod
    def build(cls, *, specification: NIIMethodologyRunSpecification) -> NIIRunEvidenceManifest:
        basis = specification.basis
        methodology = basis.methodology
        policy_references = tuple(sorted(specification.policy_references))
        evidence_references = tuple(sorted(specification.evidence_references))

        payload = {
            "schema_version": NII_REPRODUCIBILITY_SCHEMA_VERSION,
            "methodology": {
                "code": methodology.code,
                "version": methodology.version,
                "status": methodology.status.value,
                "source_reference": methodology.source_reference,
                "effective_from": (
                    methodology.effective_from.isoformat()
                    if methodology.effective_from is not None
                    else None
                ),
            },
            "projection_basis": {
                "valuation_date": basis.valuation_date.isoformat(),
                "horizon_end_date": basis.horizon_end_date.isoformat(),
                "balance_sheet_assumption": basis.balance_sheet_assumption.value,
                "shock_timing": basis.shock_timing.value,
                "source_reference": basis.source_reference,
            },
            "reporting_currency": specification.reporting_currency.value,
            "stressed_scenarios": tuple(
                scenario.value for scenario in specification.stressed_scenarios
            ),
            "policy_references": policy_references,
            "evidence_references": evidence_references,
        }
        canonical_payload = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        fingerprint = sha256(canonical_payload.encode("utf-8")).hexdigest()
        return NIIRunEvidenceManifest(
            run_reference=specification.run_reference,
            schema_version=NII_REPRODUCIBILITY_SCHEMA_VERSION,
            specification_fingerprint=fingerprint,
            canonical_payload=canonical_payload,
            policy_references=policy_references,
            evidence_references=evidence_references,
        )
