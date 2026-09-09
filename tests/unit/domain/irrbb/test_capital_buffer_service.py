from __future__ import annotations

from decimal import Decimal

import pytest

from aip.domain.irrbb import (
    CapitalBufferSchedule,
    CapitalBufferService,
    CapitalBufferTier,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
)
_PROFILE = IRRBBMethodologyProfile(
    code="TEST_IRRBB",
    version="1",
    status=IRRBBMethodologyStatus.PROPOSED,
    source_reference="TEST",
)

_SCHEDULE = CapitalBufferSchedule(
    methodology=_PROFILE,
    tiers=(
        CapitalBufferTier("LOW", Decimal("0.15"), Decimal("0.00")),
        CapitalBufferTier("MODERATE", Decimal("0.30"), Decimal("0.005")),
        CapitalBufferTier("HIGH", Decimal("0.60"), Decimal("0.015")),
        CapitalBufferTier("VERY_HIGH", None, Decimal("0.025")),
    ),
)


@pytest.mark.parametrize(
    ("exposure", "expected"),
    (
        (Decimal("0"), Decimal("0.00")),
        (Decimal("0.15"), Decimal("0.00")),
        (Decimal("0.150001"), Decimal("0.005")),
        (Decimal("0.30"), Decimal("0.005")),
        (Decimal("0.31"), Decimal("0.015")),
        (Decimal("0.60"), Decimal("0.015")),
        (Decimal("0.600001"), Decimal("0.025")),
    ),
)
def test_calculate_uses_injected_versioned_tiers(exposure: Decimal, expected: Decimal) -> None:
    result = CapitalBufferService.calculate(
        exposure_ratio=exposure,
        schedule=_SCHEDULE,
    )

    assert result.buffer_rate == expected
    assert result.methodology is _PROFILE


def test_schedule_requires_open_ended_final_tier() -> None:
    schedule = CapitalBufferSchedule(
        methodology=_PROFILE,
        tiers=(CapitalBufferTier("ONLY", Decimal("0.15"), Decimal("0")),),
    )

    with pytest.raises(ValueError, match="open-ended"):
        CapitalBufferService.calculate(
            exposure_ratio=Decimal("0.10"),
            schedule=schedule,
        )


def test_schedule_rejects_non_increasing_upper_bounds() -> None:
    schedule = CapitalBufferSchedule(
        methodology=_PROFILE,
        tiers=(
            CapitalBufferTier("A", Decimal("0.30"), Decimal("0")),
            CapitalBufferTier("B", Decimal("0.20"), Decimal("0.01")),
            CapitalBufferTier("C", None, Decimal("0.02")),
        ),
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        CapitalBufferService.calculate(
            exposure_ratio=Decimal("0.10"),
            schedule=schedule,
        )
