from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.portfolio.services.portfolio_dv01_service import PortfolioDV01Service


@dataclass(frozen=True, slots=True)
class DV01AggregateRow:
    key: str
    market_value_crc: Decimal
    dv01_crc: Decimal
    position_count: int


@dataclass(frozen=True, slots=True)
class PortfolioDV01AggregateResult:
    total_market_value_crc: Decimal
    calculated_market_value_crc: Decimal
    policy_excluded_market_value_crc: Decimal
    data_unavailable_market_value_crc: Decimal
    coverage_percent: Decimal
    total_dv01_crc: Decimal
    calculated_position_count: int
    policy_excluded_position_count: int
    data_unavailable_position_count: int
    by_currency: tuple[DV01AggregateRow, ...]
    by_issuer: tuple[DV01AggregateRow, ...]
    by_product: tuple[DV01AggregateRow, ...]
    by_bucket: tuple[DV01AggregateRow, ...]


class PortfolioDV01AggregationService:
    """Aggregate institutional DV01 results for configured portfolio positions."""

    @classmethod
    def calculate(
        cls,
        positions: list[dict[str, Any]],
        *,
        valuation_date: date,
    ) -> PortfolioDV01AggregateResult:
        rows = [(position, PortfolioDV01Service.calculate(position)) for position in positions]

        total_market_value = sum((result.market_value_crc for _, result in rows), Decimal("0"))
        calculated_market_value = sum(
            (result.market_value_crc for _, result in rows if result.status == "CALCULATED"),
            Decimal("0"),
        )
        policy_excluded_market_value = sum(
            (result.market_value_crc for _, result in rows if result.status == "POLICY_EXCLUDED"),
            Decimal("0"),
        )
        data_unavailable_market_value = sum(
            (result.market_value_crc for _, result in rows if result.status == "DATA_UNAVAILABLE"),
            Decimal("0"),
        )
        total_dv01 = sum((result.dv01_crc or Decimal("0") for _, result in rows), Decimal("0"))
        coverage_percent = (
            calculated_market_value / total_market_value * Decimal("100")
            if total_market_value > 0
            else Decimal("0")
        )

        return PortfolioDV01AggregateResult(
            total_market_value_crc=total_market_value,
            calculated_market_value_crc=calculated_market_value,
            policy_excluded_market_value_crc=policy_excluded_market_value,
            data_unavailable_market_value_crc=data_unavailable_market_value,
            coverage_percent=coverage_percent,
            total_dv01_crc=total_dv01,
            calculated_position_count=sum(1 for _, result in rows if result.status == "CALCULATED"),
            policy_excluded_position_count=sum(
                1 for _, result in rows if result.status == "POLICY_EXCLUDED"
            ),
            data_unavailable_position_count=sum(
                1 for _, result in rows if result.status == "DATA_UNAVAILABLE"
            ),
            by_currency=cls._aggregate(rows, "currency"),
            by_issuer=cls._aggregate(rows, "issuer"),
            by_product=cls._aggregate(rows, "product_code"),
            by_bucket=cls._aggregate_buckets(rows, valuation_date=valuation_date),
        )

    @classmethod
    def _aggregate_buckets(
        cls,
        rows: list[tuple[dict[str, Any], Any]],
        *,
        valuation_date: date,
    ) -> tuple[DV01AggregateRow, ...]:
        """Aggregate DV01 into institutional sensitivity buckets."""
        bucket_order = ("< 1 año", "1 a 5 años", "> 5 años")
        grouped: dict[str, dict[str, Any]] = {
            key: {
                "market_value_crc": Decimal("0"),
                "dv01_crc": Decimal("0"),
                "position_count": 0,
            }
            for key in bucket_order
        }

        for position, result in rows:
            if result.status != "CALCULATED":
                continue
            bucket_key = cls._bucket_key(position, valuation_date=valuation_date)
            if bucket_key is None:
                raise ValueError("DV01 calculated position has no valid bucket reference date")
            bucket = grouped[bucket_key]
            bucket["market_value_crc"] += result.market_value_crc
            bucket["dv01_crc"] += result.dv01_crc or Decimal("0")
            bucket["position_count"] += 1

        return tuple(
            DV01AggregateRow(
                key=key,
                market_value_crc=grouped[key]["market_value_crc"],
                dv01_crc=grouped[key]["dv01_crc"],
                position_count=grouped[key]["position_count"],
            )
            for key in bucket_order
        )

    @classmethod
    def _bucket_key(
        cls,
        position: dict[str, Any],
        *,
        valuation_date: date,
    ) -> str | None:
        is_variable = str(position.get("variable_rate_flag") or "").strip().casefold() in {
            "s",
            "si",
            "sí",
            "yes",
            "y",
            "true",
            "1",
        }
        raw_date = (
            position.get("next_repricing_date") if is_variable else position.get("maturity_date")
        )
        reference_date = cls._as_date(raw_date)
        if reference_date is None:
            return None

        one_year = cls._advance_years(valuation_date, 1)
        five_years = cls._advance_years(valuation_date, 5)
        if reference_date < one_year:
            return "< 1 año"
        if reference_date <= five_years:
            return "1 a 5 años"
        return "> 5 años"

    @staticmethod
    def _as_date(value: Any) -> date | None:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _advance_years(value: date, years: int) -> date:
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            return value.replace(year=value.year + years, month=2, day=28)

    @classmethod
    def _aggregate(
        cls,
        rows: list[tuple[dict[str, Any], Any]],
        field: str,
    ) -> tuple[DV01AggregateRow, ...]:
        grouped: dict[str, dict[str, Any]] = {}
        for position, result in rows:
            if result.status != "CALCULATED":
                continue
            key = str(position.get(field) or "UNSPECIFIED").strip()
            bucket = grouped.setdefault(
                key,
                {
                    "market_value_crc": Decimal("0"),
                    "dv01_crc": Decimal("0"),
                    "position_count": 0,
                },
            )
            bucket["market_value_crc"] += result.market_value_crc
            bucket["dv01_crc"] += result.dv01_crc or Decimal("0")
            bucket["position_count"] += 1

        result_rows = [
            DV01AggregateRow(
                key=key,
                market_value_crc=value["market_value_crc"],
                dv01_crc=value["dv01_crc"],
                position_count=value["position_count"],
            )
            for key, value in grouped.items()
        ]
        result_rows.sort(key=lambda item: abs(item.dv01_crc), reverse=True)
        return tuple(result_rows)
