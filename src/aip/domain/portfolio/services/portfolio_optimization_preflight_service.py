from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from math import isfinite
from typing import Sequence


class HistoryReadiness(StrEnum):
    READY = "READY"
    MISSING_RETURNS = "MISSING_RETURNS"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INCOMPATIBLE_CURRENCY = "INCOMPATIBLE_CURRENCY"
    POLICY_UNVERIFIED = "POLICY_UNVERIFIED"
    INVALID_DATA = "INVALID_DATA"


@dataclass(frozen=True, slots=True)
class ObservedTotalReturnSeries:
    """Observed total returns, not YTM or changes in unadjusted bond prices.

    Daily, weekly and monthly observations are accepted only at an identical
    frequency and in a common reporting currency. FX-converted total returns
    need their own auditable conversion reference.
    """

    security_key: str
    instrument_currency: str
    reporting_currency: str
    dates: tuple[date, ...]
    returns: tuple[Decimal, ...]
    frequency: str
    source_reference: str
    return_definition: str
    fx_source_reference: str = ""


@dataclass(frozen=True, slots=True)
class OptimizationPreflightResult:
    status: HistoryReadiness
    reason: str
    asset_names: tuple[str, ...] = ()
    observation_dates: tuple[date, ...] = ()
    aligned_returns: tuple[tuple[float, ...], ...] = ()
    periods_per_year: int | None = None

    @property
    def ready(self) -> bool:
        return self.status is HistoryReadiness.READY


class PortfolioOptimizationPreflightService:
    """Fail-closed, no synthetic filling or inferred covariance.

    This is a deterministic input gate. It never contacts the corporate vector,
    derives returns from YTM, or substitutes the demo portfolio for real history.
    """

    _FREQUENCIES = {"daily": 252, "weekly": 52, "monthly": 12}

    @classmethod
    def evaluate(
        cls,
        series: Sequence[ObservedTotalReturnSeries],
        *,
        cutoff: date,
        reporting_currency: str,
        policy_reference: str,
        minimum_observations: int = 30,
    ) -> OptimizationPreflightResult:
        def reject(status: HistoryReadiness, reason: str) -> OptimizationPreflightResult:
            return OptimizationPreflightResult(status=status, reason=reason)

        if not policy_reference.strip():
            return reject(HistoryReadiness.POLICY_UNVERIFIED, "Investment policy not verified")
        if (
            minimum_observations < 3
            or len(reporting_currency.strip()) != 3
            or not reporting_currency.strip().isalpha()
        ):
            return reject(HistoryReadiness.INVALID_DATA, "Invalid optimization configuration")
        records = tuple(series)
        if len(records) < 2:
            return reject(
                HistoryReadiness.MISSING_RETURNS, "At least two assets need observed returns"
            )
        names = tuple(item.security_key for item in records)
        if any(not name.strip() for name in names) or len(set(names)) != len(names):
            return reject(
                HistoryReadiness.INVALID_DATA, "Security keys must be unique and nonblank"
            )
        currency = reporting_currency.strip().upper()
        frequencies = {item.frequency for item in records}
        if len(frequencies) != 1 or next(iter(frequencies)) not in cls._FREQUENCIES:
            return reject(HistoryReadiness.INVALID_DATA, "Historical return frequency must match")
        frequency = records[0].frequency
        for item in records:
            if item.reporting_currency.strip().upper() != currency:
                return reject(
                    HistoryReadiness.INCOMPATIBLE_CURRENCY,
                    "Total returns must be translated to one reporting currency",
                )
            if (
                item.instrument_currency.strip().upper() != currency
                and not item.fx_source_reference.strip()
            ):
                return reject(
                    HistoryReadiness.INCOMPATIBLE_CURRENCY,
                    "Foreign-currency total returns require traceable FX conversion",
                )
            if item.return_definition != "TOTAL_RETURN_WITH_CASHFLOWS":
                return reject(
                    HistoryReadiness.MISSING_RETURNS,
                    "Observed total returns including cash flows are required; YTM is inadmissible",
                )
            if not item.source_reference.strip():
                return reject(
                    HistoryReadiness.MISSING_RETURNS, "Missing historical data provenance"
                )
            if len(item.dates) != len(item.returns) or not item.dates:
                return reject(
                    HistoryReadiness.MISSING_RETURNS, "Date/return observations are incomplete"
                )
            if (
                any(
                    first >= second
                    for first, second in zip(item.dates, item.dates[1:], strict=False)
                )
                or item.dates[-1] > cutoff
            ):
                return reject(
                    HistoryReadiness.INVALID_DATA,
                    "Dates must be strictly increasing and no later than cutoff",
                )
            if any(
                not isinstance(value, Decimal) or not value.is_finite() or value < -1
                for value in item.returns
            ):
                return reject(
                    HistoryReadiness.INVALID_DATA,
                    "Total returns must be finite with a floor of -100%",
                )
        common_dates = set(records[0].dates)
        for item in records[1:]:
            common_dates.intersection_update(item.dates)
        aligned_dates = tuple(sorted(common_dates))
        if len(aligned_dates) < minimum_observations:
            return reject(
                HistoryReadiness.INSUFFICIENT_HISTORY,
                "Insufficient overlapping observed dates; no interpolation or forward fill",
            )
        lookup = tuple(dict(zip(item.dates, item.returns, strict=True)) for item in records)
        rows = tuple(tuple(float(mapping[day]) for mapping in lookup) for day in aligned_dates)
        if any(not isfinite(value) for row in rows for value in row):
            return reject(HistoryReadiness.INVALID_DATA, "Numeric conversion overflowed")
        return OptimizationPreflightResult(
            status=HistoryReadiness.READY,
            reason="Aligned historical total returns passed provenance and policy gates",
            asset_names=names,
            observation_dates=aligned_dates,
            aligned_returns=rows,
            periods_per_year=cls._FREQUENCIES[frequency],
        )
