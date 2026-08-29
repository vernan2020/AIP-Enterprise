from __future__ import annotations

from calendar import monthrange
from datetime import date


def month_end(
    value: date,
) -> date:
    """
    Normalize a date to the final calendar day
    of its month.
    """
    last_day = monthrange(
        value.year,
        value.month,
    )[1]

    return date(
        value.year,
        value.month,
        last_day,
    )


def add_months_end(
    value: date,
    months: int,
) -> date:
    """
    Add calendar months and return the corresponding
    month-end date.
    """
    if months < 0:
        raise ValueError("months must be >= 0")

    normalized = month_end(value)

    absolute_month = normalized.year * 12 + normalized.month - 1 + months

    year = absolute_month // 12
    month = absolute_month % 12 + 1

    last_day = monthrange(
        year,
        month,
    )[1]

    return date(
        year,
        month,
        last_day,
    )


def build_scenario_calendar(
    *,
    dataset_as_of_date: date,
    horizon_months: int,
) -> tuple[date, ...]:
    """
    Build the common institutional scenario calendar.

    The scenario starts in the month immediately
    following the dataset as-of month.

    Example:
        dataset as-of = 2026-08-27
        horizon = 12

        calendar =
        2026-09-30 ... 2027-08-31
    """
    if horizon_months < 1:
        raise ValueError("horizon_months must be >= 1")

    anchor = month_end(dataset_as_of_date)

    return tuple(
        add_months_end(
            anchor,
            offset,
        )
        for offset in range(
            1,
            horizon_months + 1,
        )
    )


def months_between(
    origin: date,
    target: date,
) -> int:
    """
    Return the number of monthly projection steps
    from origin month-end to target month-end.

    Examples:
        2026-08-31 -> 2027-08-31 = 12
        2026-07-31 -> 2027-08-31 = 13
        2026-06-30 -> 2027-08-31 = 14
    """
    normalized_origin = month_end(origin)

    normalized_target = month_end(target)

    difference = (normalized_target.year - normalized_origin.year) * 12 + (
        normalized_target.month - normalized_origin.month
    )

    if difference < 0:
        raise ValueError("target must not precede origin")

    return difference


def required_projection_horizon(
    *,
    forecast_origin_period: date,
    scenario_calendar: tuple[date, ...],
) -> int:
    """
    Determine the statistical projection horizon
    required to reach the end of the institutional
    scenario calendar.
    """
    if not scenario_calendar:
        raise ValueError("scenario_calendar cannot be empty")

    return months_between(
        forecast_origin_period,
        scenario_calendar[-1],
    )
