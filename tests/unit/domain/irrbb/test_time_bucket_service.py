from __future__ import annotations

from datetime import date

import pytest

from aip.domain.irrbb.models import IRRBBTimeBucket
from aip.domain.irrbb.services.time_bucket_service import IRRBBTimeBucketService


@pytest.mark.parametrize(
    ("risk_date", "expected"),
    (
        (date(2026, 1, 31), IRRBBTimeBucket.DAY_1),
        (date(2026, 2, 1), IRRBBTimeBucket.DAY_1),
        (date(2026, 2, 2), IRRBBTimeBucket.DAY_1_TO_MONTH_1),
        (date(2026, 2, 28), IRRBBTimeBucket.DAY_1_TO_MONTH_1),
        (date(2026, 3, 1), IRRBBTimeBucket.MONTH_1_TO_3),
        (date(2027, 1, 31), IRRBBTimeBucket.MONTH_9_TO_YEAR_1),
        (date(2036, 1, 31), IRRBBTimeBucket.YEAR_9_TO_10),
        (date(2046, 1, 31), IRRBBTimeBucket.YEAR_15_TO_20),
        (date(2046, 2, 1), IRRBBTimeBucket.OVER_YEAR_20),
    ),
)
def test_assign_uses_calendar_boundaries(risk_date: date, expected: IRRBBTimeBucket) -> None:
    assignment = IRRBBTimeBucketService.assign(
        valuation_date=date(2026, 1, 31),
        risk_date=risk_date,
    )

    assert assignment.bucket is expected


def test_assign_rejects_past_risk_date() -> None:
    with pytest.raises(ValueError, match="before valuation_date"):
        IRRBBTimeBucketService.assign(
            valuation_date=date(2026, 8, 31),
            risk_date=date(2026, 8, 30),
        )


def test_all_nineteen_buckets_have_unique_ordinals() -> None:
    valuation = date(2026, 1, 1)
    risk_dates = (
        date(2026, 1, 2),
        date(2026, 1, 3),
        date(2026, 2, 2),
        date(2026, 4, 2),
        date(2026, 7, 2),
        date(2026, 10, 2),
        date(2027, 1, 2),
        date(2027, 7, 2),
        date(2028, 1, 2),
        date(2029, 1, 2),
        date(2030, 1, 2),
        date(2031, 1, 2),
        date(2032, 1, 2),
        date(2033, 1, 2),
        date(2034, 1, 2),
        date(2035, 1, 2),
        date(2036, 1, 2),
        date(2041, 1, 2),
        date(2046, 1, 2),
    )

    assignments = IRRBBTimeBucketService.assign_many(
        valuation_date=valuation,
        risk_dates=risk_dates,
    )

    assert tuple(item.ordinal for item in assignments) == tuple(range(1, 20))
    assert len({item.bucket for item in assignments}) == 19
