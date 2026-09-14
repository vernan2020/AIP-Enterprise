from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from aip.domain.irrbb.models import (
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
)
from aip.domain.irrbb.nii import (
    NIIBalanceSheetAssumption,
    NIIProjectionBasis,
    NIIShockTiming,
)
from aip.domain.irrbb.nii_reproducibility import NIIRunEvidenceManifest
from aip.domain.irrbb.nii_run_specification import NIIMethodologyRunSpecification
from aip.domain.irrbb.services.nii_run_reproducibility_service import (
    NIIRunReproducibilityService,
)
from aip.shared.money import Currency


def _specification(run_reference: str = "run:001") -> NIIMethodologyRunSpecification:
    return NIIMethodologyRunSpecification(
        run_reference=run_reference,
        basis=NIIProjectionBasis(
            methodology=IRRBBMethodologyProfile(
                code="INTERNAL-NII",
                version="2026.09",
                status=IRRBBMethodologyStatus.INTERNAL,
                source_reference="policy:nii:v1",
                effective_from=date(2026, 9, 1),
            ),
            valuation_date=date(2026, 9, 11),
            horizon_end_date=date(2027, 9, 11),
            balance_sheet_assumption=NIIBalanceSheetAssumption.CONSTANT,
            shock_timing=NIIShockTiming.INSTANTANEOUS,
            source_reference="basis:approved:v1",
        ),
        reporting_currency=Currency.CRC,
        stressed_scenarios=(IRRBBScenario.PARALLEL_UP, IRRBBScenario.PARALLEL_DOWN),
        policy_references=("policy:b", "policy:a"),
        evidence_references=("evidence:2", "evidence:1"),
    )


def test_same_methodological_perimeter_has_same_fingerprint_across_runs() -> None:
    first = NIIRunReproducibilityService.build(specification=_specification("run:001"))
    second = NIIRunReproducibilityService.build(specification=_specification("run:002"))

    assert first.run_reference != second.run_reference
    assert first.specification_fingerprint == second.specification_fingerprint
    assert first.canonical_payload == second.canonical_payload


def test_reference_order_does_not_change_fingerprint() -> None:
    first_spec = _specification()
    second_spec = replace(
        first_spec,
        policy_references=tuple(reversed(first_spec.policy_references)),
        evidence_references=tuple(reversed(first_spec.evidence_references)),
    )

    first = NIIRunReproducibilityService.build(specification=first_spec)
    second = NIIRunReproducibilityService.build(specification=second_spec)

    assert first.specification_fingerprint == second.specification_fingerprint
    assert first.policy_references == ("policy:a", "policy:b")
    assert first.evidence_references == ("evidence:1", "evidence:2")


def test_stress_order_is_part_of_reproducibility_identity() -> None:
    specification = _specification()
    reordered = replace(
        specification,
        stressed_scenarios=tuple(reversed(specification.stressed_scenarios)),
    )

    first = NIIRunReproducibilityService.build(specification=specification)
    second = NIIRunReproducibilityService.build(specification=reordered)

    assert first.specification_fingerprint != second.specification_fingerprint


def test_basis_change_changes_reproducibility_identity() -> None:
    specification = _specification()
    changed = replace(
        specification,
        basis=replace(
            specification.basis,
            horizon_end_date=date(2028, 9, 11),
        ),
    )

    first = NIIRunReproducibilityService.build(specification=specification)
    second = NIIRunReproducibilityService.build(specification=changed)

    assert first.specification_fingerprint != second.specification_fingerprint


def test_manifest_rejects_tampered_fingerprint() -> None:
    manifest = NIIRunReproducibilityService.build(specification=_specification())

    with pytest.raises(ValueError, match="fingerprint does not match"):
        NIIRunEvidenceManifest(
            run_reference=manifest.run_reference,
            schema_version=manifest.schema_version,
            specification_fingerprint="0" * 64,
            canonical_payload=manifest.canonical_payload,
            policy_references=manifest.policy_references,
            evidence_references=manifest.evidence_references,
        )
