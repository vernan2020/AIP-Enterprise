from __future__ import annotations

from decimal import Decimal

import pytest

from aip.domain.irrbb.services.capital_buffer_service import CapitalBufferService
from aip.domain.irrbb import models


_PROFILE = models.IRRBBMethodologyProfile(
    code="TEST_IRRBB",
    version="1",
    status=models.IRRBBMethodologyStatus.PROPOSED,
    source_reference="TEST",
)

_SCHEDULE = models.CapitalBufferSchedule(
    methodology=_PROFILE,
    tiers=(
        models.CapitalBufferTier("LOW", Decimal("0.15"), Decimal("0.00")),
        models.CapitalBufferTier("MODERATE", Decimal("0.30"), Decimal("0.005")),
        models.CapitalBufferTier("HIGH", Decimal("0.60"), Decimal("0.015")),
        models.CapitalBufferTier("VERY_HIGH", None, Decimal("0.025")),
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
    schedule = models.CapitalBufferSchedule(
        methodology=_PROFILE,
        tiers=(models.CapitalBufferTier("ONLY", Decimal("0.15"), Decimal("0")),),
    )

    with pytest.raises(ValueError, match="open-ended"):
        CapitalBufferService.calculate(
            exposure_ratio=Decimal("0.10"),
            schedule=schedule,
        )


def test_schedule_rejects_non_increasing_upper_bounds() -> None:
    schedule = models.CapitalBufferSchedule(
        methodology=_PROFILE,
        tiers=(
            models.CapitalBufferTier("A", Decimal("0.30"), Decimal("0")),
            models.CapitalBufferTier("B", Decimal("0.20"), Decimal("0.01")),
            models.CapitalBufferTier("C", None, Decimal("0.02")),
        ),
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        CapitalBufferService.calculate(
            exposure_ratio=Decimal("0.10"),
            schedule=schedule,
        )
