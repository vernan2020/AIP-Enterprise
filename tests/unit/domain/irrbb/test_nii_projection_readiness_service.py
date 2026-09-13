from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBInstrumentClass,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.nii_readiness import (
    NIIProjectionCapabilityEvidence,
    NIIProjectionEvidenceAlternative,
    NIIProjectionEvidenceKey,
    NIIProjectionReadinessStatus,
    NIIProjectionRequirement,
    NIIProjectionRequirementProfile,
    NIIProjectionScopeStatus,
)
from aip.domain.irrbb.services.nii_projection_readiness_service import (
    NIIProjectionReadinessService,
)
from aip.shared.money import Currency, Money


def _position(**overrides: object) -> BankingBookPosition:
    values: dict[str, object] = {
        "position_id": "p1",
        "product_type": "TEST",
        "side": BankingBookSide.ASSET,
        "currency": Currency.CRC,
        "principal": Money(Decimal("1000"), Currency.CRC),
        "rate_type": RateType.FLOATING,
        "maturity_date": date(2027, 9, 10),
        "source_reference": "source:p1",
        "contractual_rate": None,
        "reference_rate": "TRI_CRC",
        "spread": Decimal("0.015"),
        "next_repricing_date": date(2026, 10, 10),
        "repricing_frequency_months": 1,
        "payment_frequency_months": 1,
        "instrument_class": IRRBBInstrumentClass.CREDIT,
        "payment_structure": PaymentStructure.AMORTIZING,
    }
    values.update(overrides)
    return BankingBookPosition(**values)  # type: ignore[arg-type]


def _requirement(
    requirement_id: str,
    *alternatives: frozenset[NIIProjectionEvidenceKey],
) -> NIIProjectionRequirement:
    return NIIProjectionRequirement(
        requirement_id=requirement_id,
        alternatives=tuple(NIIProjectionEvidenceAlternative(keys=item) for item in alternatives),
        message=f"Evidence required for {requirement_id}.",
    )


def _profile(*requirements: NIIProjectionRequirement) -> NIIProjectionRequirementProfile:
    return NIIProjectionRequirementProfile(
        strategy_reference="strategy:floating-credit:v1",
        source_reference="policy:nii:floating-credit:v1",
        scope_status=NIIProjectionScopeStatus.INCLUDED,
        requirements=tuple(requirements),
    )


def test_ready_when_every_declared_requirement_is_satisfied() -> None:
    profile = _profile(
        _requirement(
            "rate-basis",
            frozenset({NIIProjectionEvidenceKey.CONTRACTUAL_RATE}),
            frozenset(
                {
                    NIIProjectionEvidenceKey.REFERENCE_RATE,
                    NIIProjectionEvidenceKey.SPREAD,
                }
            ),
        ),
        _requirement(
            "reset-basis",
            frozenset(
                {
                    NIIProjectionEvidenceKey.NEXT_REPRICING_DATE,
                    NIIProjectionEvidenceKey.REPRICING_FREQUENCY_MONTHS,
                }
            ),
        ),
        _requirement(
            "forward-curve",
            frozenset({NIIProjectionEvidenceKey.FORWARD_REFERENCE_RATE_CURVE}),
        ),
    )
    capabilities = (
        NIIProjectionCapabilityEvidence(
            key=NIIProjectionEvidenceKey.FORWARD_REFERENCE_RATE_CURVE,
            source_reference="curve:approved:tri-crc:v1",
        ),
    )

    result = NIIProjectionReadinessService.assess(
        position=_position(),
        profile=profile,
        capabilities=capabilities,
    )

    assert result.status is NIIProjectionReadinessStatus.READY
    assert result.is_ready
    assert result.findings == ()
    assert result.strategy_reference == profile.strategy_reference
    assert result.profile_source_reference == profile.source_reference


def test_any_declared_alternative_can_satisfy_requirement() -> None:
    profile = _profile(
        _requirement(
            "rate-basis",
            frozenset({NIIProjectionEvidenceKey.CONTRACTUAL_RATE}),
            frozenset(
                {
                    NIIProjectionEvidenceKey.REFERENCE_RATE,
                    NIIProjectionEvidenceKey.SPREAD,
                }
            ),
        )
    )

    result = NIIProjectionReadinessService.assess(
        position=_position(reference_rate=None, spread=None, contractual_rate=Decimal("0.04")),
        profile=profile,
    )

    assert result.status is NIIProjectionReadinessStatus.READY


def test_zero_decimal_is_present_evidence_not_treated_as_missing() -> None:
    profile = _profile(
        _requirement(
            "contractual-rate",
            frozenset({NIIProjectionEvidenceKey.CONTRACTUAL_RATE}),
        ),
        _requirement(
            "spread",
            frozenset({NIIProjectionEvidenceKey.SPREAD}),
        ),
    )

    result = NIIProjectionReadinessService.assess(
        position=_position(contractual_rate=Decimal("0"), spread=Decimal("0")),
        profile=profile,
    )

    assert result.status is NIIProjectionReadinessStatus.READY


def test_missing_requirement_reports_each_permitted_alternative() -> None:
    profile = _profile(
        _requirement(
            "rate-basis",
            frozenset({NIIProjectionEvidenceKey.CONTRACTUAL_RATE}),
            frozenset(
                {
                    NIIProjectionEvidenceKey.REFERENCE_RATE,
                    NIIProjectionEvidenceKey.SPREAD,
                }
            ),
        )
    )

    result = NIIProjectionReadinessService.assess(
        position=_position(contractual_rate=None, reference_rate=None, spread=None),
        profile=profile,
    )

    assert result.status is NIIProjectionReadinessStatus.BLOCKED
    assert not result.is_ready
    assert len(result.findings) == 1
    assert result.findings[0].requirement_id == "rate-basis"
    assert result.findings[0].missing_alternatives == (
        (NIIProjectionEvidenceKey.CONTRACTUAL_RATE,),
        (
            NIIProjectionEvidenceKey.REFERENCE_RATE,
            NIIProjectionEvidenceKey.SPREAD,
        ),
    )


def test_missing_external_capability_cannot_be_satisfied_by_position_fields() -> None:
    profile = _profile(
        _requirement(
            "forward-curve",
            frozenset({NIIProjectionEvidenceKey.FORWARD_REFERENCE_RATE_CURVE}),
        )
    )

    result = NIIProjectionReadinessService.assess(position=_position(), profile=profile)

    assert result.status is NIIProjectionReadinessStatus.BLOCKED
    assert result.findings[0].missing_alternatives == (
        (NIIProjectionEvidenceKey.FORWARD_REFERENCE_RATE_CURVE,),
    )


def test_external_capability_cannot_impersonate_position_evidence() -> None:
    with pytest.raises(ValueError, match="position evidence cannot be supplied"):
        NIIProjectionCapabilityEvidence(
            key=NIIProjectionEvidenceKey.CONTRACTUAL_RATE,
            source_reference="policy:not-a-contractual-rate",
        )


def test_duplicate_capability_evidence_is_rejected() -> None:
    evidence = NIIProjectionCapabilityEvidence(
        key=NIIProjectionEvidenceKey.EXPLICIT_CONTRACTUAL_SCHEDULE,
        source_reference="schedule:approved:v1",
    )

    with pytest.raises(ValueError, match="duplicate NII projection capability evidence"):
        NIIProjectionReadinessService.assess(
            position=_position(),
            profile=_profile(),
            capabilities=(evidence, evidence),
        )


def test_unclassified_payment_structure_is_not_present_evidence() -> None:
    profile = _profile(
        _requirement(
            "payment-structure",
            frozenset({NIIProjectionEvidenceKey.PAYMENT_STRUCTURE_CLASSIFIED}),
        )
    )

    result = NIIProjectionReadinessService.assess(
        position=_position(payment_structure=PaymentStructure.OTHER),
        profile=profile,
    )

    assert result.status is NIIProjectionReadinessStatus.BLOCKED


def test_unclassified_instrument_class_is_not_present_evidence() -> None:
    profile = _profile(
        _requirement(
            "instrument-class",
            frozenset({NIIProjectionEvidenceKey.INSTRUMENT_CLASS_CLASSIFIED}),
        )
    )

    result = NIIProjectionReadinessService.assess(
        position=_position(instrument_class=IRRBBInstrumentClass.OTHER),
        profile=profile,
    )

    assert result.status is NIIProjectionReadinessStatus.BLOCKED


def test_excluded_profile_returns_explicit_exclusion_without_requirements() -> None:
    profile = NIIProjectionRequirementProfile(
        strategy_reference="strategy:out-of-scope:v1",
        source_reference="policy:nii:scope:v1",
        scope_status=NIIProjectionScopeStatus.EXCLUDED,
        exclusion_reason="Position is outside the approved NII measurement perimeter.",
    )

    result = NIIProjectionReadinessService.assess(position=_position(), profile=profile)

    assert result.status is NIIProjectionReadinessStatus.EXCLUDED
    assert not result.is_ready
    assert result.findings == ()
    assert result.exclusion_reason == profile.exclusion_reason


def test_excluded_profile_cannot_hide_requirements() -> None:
    with pytest.raises(
        ValueError, match="excluded NII projection profile cannot declare requirements"
    ):
        NIIProjectionRequirementProfile(
            strategy_reference="strategy:excluded:v1",
            source_reference="policy:scope:v1",
            scope_status=NIIProjectionScopeStatus.EXCLUDED,
            requirements=(
                _requirement(
                    "hidden",
                    frozenset({NIIProjectionEvidenceKey.MATURITY_DATE}),
                ),
            ),
            exclusion_reason="Excluded by approved policy.",
        )


def test_duplicate_requirement_ids_are_rejected() -> None:
    requirement = _requirement(
        "duplicate",
        frozenset({NIIProjectionEvidenceKey.MATURITY_DATE}),
    )

    with pytest.raises(ValueError, match="duplicate NII projection requirement_id"):
        _profile(requirement, requirement)


def test_duplicate_requirement_alternatives_are_rejected() -> None:
    alternative = frozenset({NIIProjectionEvidenceKey.MATURITY_DATE})

    with pytest.raises(ValueError, match="duplicate NII projection evidence alternatives"):
        _requirement("duplicate-alternative", alternative, alternative)
