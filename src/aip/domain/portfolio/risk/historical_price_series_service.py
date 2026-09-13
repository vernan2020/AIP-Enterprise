from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from aip.domain.portfolio.risk.historical_price_series import (
    HistoricalPriceObservation,
    HistoricalPriceSeries,
)


class HistoricalPriceSeriesService:
    """Normalize real observations to one explicit institutional calendar.

    Missing history prior to a security's first real observation is filled with
    that first observed price, as required by the approved new-title VeR rule.
    Calendar gaps after inception use the last real price known on or before the
    target date and are explicitly marked synthetic; no future observation is
    ever used to fill an earlier date.
    """

    @classmethod
    def build(
        cls,
        *,
        security_key: str,
        observations: Iterable[HistoricalPriceObservation],
        valuation_date: date,
        target_dates: tuple[date, ...],
    ) -> HistoricalPriceSeries:
        if not security_key.strip():
            raise ValueError("security_key is required")
        if not isinstance(valuation_date, date):
            raise TypeError("valuation_date must be datetime.date")
        if not target_dates:
            raise ValueError("target_dates cannot be empty")
        if tuple(sorted(target_dates)) != target_dates or len(set(target_dates)) != len(
            target_dates
        ):
            raise ValueError("target_dates must be unique and ascending")
        if target_dates[-1] > valuation_date:
            raise ValueError("target_dates cannot exceed valuation_date")

        real_by_date: dict[date, HistoricalPriceObservation] = {}
        for item in observations:
            if not isinstance(item, HistoricalPriceObservation):
                raise TypeError("observations must contain HistoricalPriceObservation")
            if item.valuation_date > valuation_date or item.market_price <= 0:
                continue
            existing = real_by_date.get(item.valuation_date)
            if existing is not None and existing.market_price != item.market_price:
                raise ValueError(
                    f"ambiguous market prices for {security_key} on {item.valuation_date.isoformat()}"
                )
            real_by_date[item.valuation_date] = item

        if not real_by_date:
            raise ValueError("at least one positive real price observation is required")

        real_dates = tuple(sorted(real_by_date))
        first_real = real_by_date[real_dates[0]]
        aligned: list[HistoricalPriceObservation] = []
        last_real: HistoricalPriceObservation | None = None
        real_index = 0

        for target_date in target_dates:
            while real_index < len(real_dates) and real_dates[real_index] <= target_date:
                last_real = real_by_date[real_dates[real_index]]
                real_index += 1

            exact = real_by_date.get(target_date)
            if exact is not None:
                aligned.append(exact)
                continue

            if target_date < first_real.valuation_date:
                aligned.append(
                    HistoricalPriceObservation(
                        valuation_date=target_date,
                        market_price=first_real.market_price,
                        source=f"BACKFILL_INITIAL:{first_real.source}",
                        synthetic=True,
                    )
                )
                continue

            if last_real is None:
                raise ValueError(f"no price available on or before {target_date.isoformat()}")

            aligned.append(
                HistoricalPriceObservation(
                    valuation_date=target_date,
                    market_price=Decimal(last_real.market_price),
                    source=f"CARRY_FORWARD_GAP:{last_real.source}",
                    synthetic=True,
                )
            )

        return HistoricalPriceSeries(
            security_key=security_key,
            valuation_date=valuation_date,
            observations=tuple(aligned),
        )
