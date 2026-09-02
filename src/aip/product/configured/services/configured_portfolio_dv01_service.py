from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.portfolio.services.portfolio_dv01_aggregation_service import (
    DV01AggregateRow,
    PortfolioDV01AggregationService,
)
from aip.domain.portfolio.services.portfolio_dv01_bucket_service import (
    PortfolioDV01BucketService,
)
from aip.domain.portfolio.services.portfolio_dv01_service import PortfolioDV01Service
from aip.domain.portfolio.services.portfolio_security_identity_service import (
    PortfolioSecurityIdentityService,
)
from aip.product.configured.protocols import PortfolioDataProvider


@dataclass(frozen=True, slots=True)
class ConfiguredPortfolioDV01TitleDetail:
    """Detalle DV01 agregado a la misma identidad de título usada por el VeR."""

    security_key: str
    series: str
    issuer: str
    currency: str
    market_value_crc: Decimal
    modified_duration: Decimal | None
    dv01_crc: Decimal | None
    bucket: str
    position_count: int
    status: str


@dataclass(frozen=True, slots=True)
class ConfiguredPortfolioDV01Result:
    valuation_date: object
    total_market_value_crc: Decimal
    calculated_market_value_crc: Decimal
    policy_excluded_market_value_crc: Decimal
    data_unavailable_market_value_crc: Decimal
    coverage_percent: Decimal
    total_dv01_crc: Decimal
    dv01_crc_currency: Decimal
    dv01_usd_currency: Decimal
    calculated_position_count: int
    policy_excluded_position_count: int
    data_unavailable_position_count: int
    by_currency: tuple[DV01AggregateRow, ...]
    by_issuer: tuple[DV01AggregateRow, ...]
    by_product: tuple[DV01AggregateRow, ...]
    by_bucket: tuple[DV01AggregateRow, ...]
    status: str
    title_details: tuple[ConfiguredPortfolioDV01TitleDetail, ...] = ()


class ConfiguredPortfolioDV01Service:
    """Servicio de aplicación para DV01 institucional del portafolio."""

    def __init__(self, portfolio_provider: PortfolioDataProvider) -> None:
        self._portfolio_provider = portfolio_provider

    def calculate(self) -> ConfiguredPortfolioDV01Result:
        portfolio = self._portfolio_provider.get_portfolio()
        positions = [
            position
            for position in portfolio.get("positions", [])
            if isinstance(position, dict)
        ]
        raw_valuation_date = portfolio.get("valuation_date")
        if isinstance(raw_valuation_date, date):
            valuation_date = raw_valuation_date
        elif isinstance(raw_valuation_date, str):
            valuation_date = date.fromisoformat(raw_valuation_date[:10])
        else:
            raise ValueError(
                "Portfolio valuation date is unavailable for DV01 bucket aggregation"
            )

        aggregate = PortfolioDV01AggregationService.calculate(
            positions,
            valuation_date=valuation_date,
        )
        dv01_crc_currency = Decimal("0")
        dv01_usd_currency = Decimal("0")
        for row in aggregate.by_currency:
            key = row.key.strip().casefold()
            if key in {"crc", "colon", "colones", "mn"}:
                dv01_crc_currency += row.dv01_crc
            elif key in {"dolar", "dólar", "usd", "me"}:
                dv01_usd_currency += row.dv01_crc

        status = (
            "CALCULATED"
            if aggregate.data_unavailable_position_count == 0
            else "CALCULATED_WITH_DATA_GAPS"
        )
        return ConfiguredPortfolioDV01Result(
            valuation_date=portfolio.get("valuation_date"),
            total_market_value_crc=aggregate.total_market_value_crc,
            calculated_market_value_crc=aggregate.calculated_market_value_crc,
            policy_excluded_market_value_crc=aggregate.policy_excluded_market_value_crc,
            data_unavailable_market_value_crc=aggregate.data_unavailable_market_value_crc,
            coverage_percent=aggregate.coverage_percent,
            total_dv01_crc=aggregate.total_dv01_crc,
            dv01_crc_currency=dv01_crc_currency,
            dv01_usd_currency=dv01_usd_currency,
            calculated_position_count=aggregate.calculated_position_count,
            policy_excluded_position_count=aggregate.policy_excluded_position_count,
            data_unavailable_position_count=aggregate.data_unavailable_position_count,
            by_currency=aggregate.by_currency,
            by_issuer=aggregate.by_issuer,
            by_product=aggregate.by_product,
            by_bucket=aggregate.by_bucket,
            status=status,
            title_details=self._build_title_details(
                positions,
                valuation_date=valuation_date,
            ),
        )

    @classmethod
    def _build_title_details(
        cls,
        positions: list[dict[str, Any]],
        *,
        valuation_date: date,
    ) -> tuple[ConfiguredPortfolioDV01TitleDetail, ...]:
        grouped: dict[str, dict[str, Any]] = {}

        for position in positions:
            security_key = PortfolioSecurityIdentityService.from_position(position)
            result = PortfolioDV01Service.calculate(position)
            market_value = result.market_value_crc
            duration = result.modified_duration
            bucket = (
                PortfolioDV01BucketService.bucket_key(
                    position,
                    valuation_date=valuation_date,
                )
                if result.status == "CALCULATED"
                else None
            )

            item = grouped.setdefault(
                security_key,
                {
                    "series": str(position.get("series") or "").strip(),
                    "issuer": str(position.get("issuer") or "").strip(),
                    "currency": str(position.get("currency") or "").strip(),
                    "market_value_crc": Decimal("0"),
                    "duration_weighted_sum": Decimal("0"),
                    "duration_weight": Decimal("0"),
                    "dv01_crc": Decimal("0"),
                    "calculated_count": 0,
                    "policy_excluded_count": 0,
                    "data_unavailable_count": 0,
                    "position_count": 0,
                    "buckets": set(),
                },
            )
            item["market_value_crc"] += market_value
            item["position_count"] += 1

            if duration is not None and market_value > 0:
                item["duration_weighted_sum"] += duration * market_value
                item["duration_weight"] += market_value

            if result.status == "CALCULATED":
                item["calculated_count"] += 1
                item["dv01_crc"] += result.dv01_crc or Decimal("0")
                if bucket:
                    item["buckets"].add(bucket)
            elif result.status == "POLICY_EXCLUDED":
                item["policy_excluded_count"] += 1
            else:
                item["data_unavailable_count"] += 1

        details: list[ConfiguredPortfolioDV01TitleDetail] = []
        for security_key, item in grouped.items():
            duration_weight = item["duration_weight"]
            modified_duration = (
                item["duration_weighted_sum"] / duration_weight
                if duration_weight > 0
                else None
            )
            calculated_count = int(item["calculated_count"])
            policy_excluded_count = int(item["policy_excluded_count"])
            data_unavailable_count = int(item["data_unavailable_count"])
            if calculated_count and not data_unavailable_count and not policy_excluded_count:
                detail_status = "CALCULATED"
            elif calculated_count:
                detail_status = "CALCULATED_WITH_DATA_GAPS"
            elif policy_excluded_count and not data_unavailable_count:
                detail_status = "POLICY_EXCLUDED"
            else:
                detail_status = "DATA_UNAVAILABLE"

            buckets = tuple(sorted(item["buckets"]))
            if len(buckets) == 1:
                bucket_label = buckets[0]
            elif len(buckets) > 1:
                bucket_label = "MIXTO"
            else:
                bucket_label = "N/A"

            details.append(
                ConfiguredPortfolioDV01TitleDetail(
                    security_key=security_key,
                    series=item["series"],
                    issuer=item["issuer"],
                    currency=item["currency"],
                    market_value_crc=item["market_value_crc"],
                    modified_duration=modified_duration,
                    dv01_crc=(item["dv01_crc"] if calculated_count else None),
                    bucket=bucket_label,
                    position_count=int(item["position_count"]),
                    status=detail_status,
                )
            )

        details.sort(
            key=lambda item: abs(item.dv01_crc or Decimal("0")),
            reverse=True,
        )
        return tuple(details)
