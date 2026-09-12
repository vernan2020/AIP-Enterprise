from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from aip.domain.irrbb.models import IRRBBTimeBucket, TimeBucketAssignment


class IRRBBTimeBucketService:
    """Map repricing-risk dates into the nineteen target IRRBB time buckets.

    Calendar-month boundaries are used rather than fixed 30-day approximations.
    A risk date equal to the valuation date is conservatively included in the
    first (overnight) bucket. Dates before the valuation date are invalid.
    """

    _MONTH_BUCKETS: tuple[tuple[int, IRRBBTimeBucket, str], ...] = (
        (1, IRRBBTimeBucket.DAY_1_TO_MONTH_1, "1 día a 1 mes"),
        (3, IRRBBTimeBucket.MONTH_1_TO_3, "1 a 3 meses"),
        (6, IRRBBTimeBucket.MONTH_3_TO_6, "3 a 6 meses"),
        (9, IRRBBTimeBucket.MONTH_6_TO_9, "6 a 9 meses"),
        (12, IRRBBTimeBucket.MONTH_9_TO_YEAR_1, "9 a 12 meses"),
        (18, IRRBBTimeBucket.YEAR_1_TO_1_5, "1 a 1.5 años"),
        (24, IRRBBTimeBucket.YEAR_1_5_TO_2, "1.5 a 2 años"),
        (36, IRRBBTimeBucket.YEAR_2_TO_3, "2 a 3 años"),
        (48, IRRBBTimeBucket.YEAR_3_TO_4, "3 a 4 años"),
        (60, IRRBBTimeBucket.YEAR_4_TO_5, "4 a 5 años"),
        (72, IRRBBTimeBucket.YEAR_5_TO_6, "5 a 6 años"),
        (84, IRRBBTimeBucket.YEAR_6_TO_7, "6 a 7 años"),
        (96, IRRBBTimeBucket.YEAR_7_TO_8, "7 a 8 años"),
        (108, IRRBBTimeBucket.YEAR_8_TO_9, "8 a 9 años"),
        (120, IRRBBTimeBucket.YEAR_9_TO_10, "9 a 10 años"),
        (180, IRRBBTimeBucket.YEAR_10_TO_15, "10 a 15 años"),
        (240, IRRBBTimeBucket.YEAR_15_TO_20, "15 a 20 años"),
    )

    @classmethod
    def assign(cls, *, valuation_date: date, risk_date: date) -> TimeBucketAssignment:
        if risk_date < valuation_date:
            raise ValueError("risk_date cannot be before valuation_date")

        if risk_date <= valuation_date + timedelta(days=1):
            return TimeBucketAssignment(
                bucket=IRRBBTimeBucket.DAY_1,
                ordinal=1,
                label="Overnight",
                valuation_date=valuation_date,
                risk_date=risk_date,
            )

        for ordinal, (months, bucket, label) in enumerate(cls._MONTH_BUCKETS, start=2):
            if risk_date <= cls._add_months(valuation_date, months):
                return TimeBucketAssignment(
                    bucket=bucket,
                    ordinal=ordinal,
                    label=label,
                    valuation_date=valuation_date,
                    risk_date=risk_date,
                )

        return TimeBucketAssignment(
            bucket=IRRBBTimeBucket.OVER_YEAR_20,
            ordinal=19,
            label="Más de 20 años",
            valuation_date=valuation_date,
            risk_date=risk_date,
        )

    @classmethod
    def assign_many(
        cls,
        *,
        valuation_date: date,
        risk_dates: tuple[date, ...],
    ) -> tuple[TimeBucketAssignment, ...]:
        return tuple(
            cls.assign(valuation_date=valuation_date, risk_date=value) for value in risk_dates
        )

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        month_index = value.year * 12 + value.month - 1 + months
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(value.day, monthrange(year, month)[1])
        return date(year, month, day)
