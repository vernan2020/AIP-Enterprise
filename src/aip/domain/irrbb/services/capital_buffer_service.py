from __future__ import annotations

from decimal import Decimal

from aip.domain.irrbb.models import (
    CapitalBufferResult,
    CapitalBufferSchedule,
    CapitalBufferTier,
)


class CapitalBufferService:
    """Resolve an IRRBB capital buffer from an injected, versioned tier schedule."""

    @classmethod
    def calculate(
        cls,
        *,
        exposure_ratio: Decimal,
        schedule: CapitalBufferSchedule,
    ) -> CapitalBufferResult:
        if exposure_ratio < 0:
            raise ValueError("exposure_ratio cannot be negative")
        cls._validate_schedule(schedule)

        for tier in schedule.tiers:
            if tier.upper_bound_ratio is None or exposure_ratio <= tier.upper_bound_ratio:
                return CapitalBufferResult(
                    methodology=schedule.methodology,
                    exposure_ratio=exposure_ratio,
                    buffer_rate=tier.buffer_rate,
                    matched_tier_label=tier.label,
                )
        raise RuntimeError("capital-buffer schedule does not cover the exposure ratio")

    @staticmethod
    def _validate_schedule(schedule: CapitalBufferSchedule) -> None:
        if not schedule.tiers:
            raise ValueError("capital-buffer schedule requires at least one tier")

        previous = Decimal("-1")
        open_ended_seen = False
        for index, tier in enumerate(schedule.tiers):
            CapitalBufferService._validate_tier_order(
                tier=tier,
                index=index,
                total=len(schedule.tiers),
                previous=previous,
                open_ended_seen=open_ended_seen,
            )
            if tier.upper_bound_ratio is None:
                open_ended_seen = True
            else:
                previous = tier.upper_bound_ratio

        if not open_ended_seen:
            raise ValueError("capital-buffer schedule must end with an open-ended tier")

    @staticmethod
    def _validate_tier_order(
        *,
        tier: CapitalBufferTier,
        index: int,
        total: int,
        previous: Decimal,
        open_ended_seen: bool,
    ) -> None:
        if open_ended_seen:
            raise ValueError("no tier may follow an open-ended tier")
        if tier.upper_bound_ratio is None:
            if index != total - 1:
                raise ValueError("open-ended capital-buffer tier must be last")
            return
        if tier.upper_bound_ratio <= previous:
            raise ValueError("capital-buffer upper bounds must be strictly increasing")
