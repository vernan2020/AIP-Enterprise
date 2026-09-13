from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.financial_math.curves.nelson_siegel import nelson_siegel_zero_rate


@dataclass(frozen=True, slots=True)
class InstitutionalRelativeValueResult:
    curve_id: str
    isin: str
    series: str
    issuer: str
    currency: str
    product_code: str
    maturity_date: date
    tenor: Decimal
    position_count: int
    market_value_crc: Decimal
    market_yield: Decimal
    curve_yield: Decimal
    spread_bp: Decimal
    classification: str


class InstitutionalRelativeValueService:
    """Calculate consolidated relative value against institutional Nelson-Siegel curves."""

    CHEAP_THRESHOLD_BP = Decimal("10")
    RICH_THRESHOLD_BP = Decimal("-10")

    _CURVE_MAPPING = {
        ("G", "CRC", "tp"): "GOBIERNO_CRC",
        ("G", "DOLAR", "tp$"): "GOBIERNO_USD",
        ("BCCR", "CRC", "bem"): "BCCR_CRC",
    }

    def calculate(
        self,
        positions: list[dict[str, Any]],
        curves: list[dict[str, Any]],
        cutoff_date: date,
    ) -> tuple[InstitutionalRelativeValueResult, ...]:
        curve_index = {
            str(curve_id): curve
            for curve in curves
            if isinstance(curve, dict)
            and (curve_id := curve.get("curve_id"))
            and isinstance(curve.get("nelson_siegel"), dict)
        }

        groups: dict[
            tuple[str, str, str, date],
            list[dict[str, Any]],
        ] = defaultdict(list)

        metadata: dict[
            tuple[str, str, str, date],
            dict[str, str],
        ] = {}

        for position in positions:
            curve_id = self._resolve_curve_id(position)

            if curve_id is None or curve_id not in curve_index:
                continue

            if str(position.get("match_status", "")).upper() != "MATCHED":
                continue

            maturity = position.get("maturity_date")
            market_yield = position.get("market_yield")
            market_value = position.get("market_value_crc")

            if maturity is None or market_yield is None or market_value is None:
                continue

            yield_value = Decimal(str(market_yield))
            market_value_value = Decimal(str(market_value))

            if yield_value <= 0 or market_value_value <= 0:
                continue

            isin = str(position.get("isin") or "")
            series = str(position.get("series") or "")

            key = (
                curve_id,
                isin,
                series,
                maturity,
            )

            groups[key].append(
                {
                    "market_yield": yield_value,
                    "market_value_crc": market_value_value,
                }
            )

            metadata[key] = {
                "issuer": str(position.get("issuer") or ""),
                "currency": str(position.get("currency") or ""),
                "product_code": str(position.get("product_code") or ""),
            }

        results: list[InstitutionalRelativeValueResult] = []

        for key, grouped_positions in groups.items():
            curve_id, isin, series, maturity = key
            meta = metadata[key]

            total_market_value = sum(item["market_value_crc"] for item in grouped_positions)

            weighted_market_yield = (
                sum(item["market_yield"] * item["market_value_crc"] for item in grouped_positions)
                / total_market_value
            )

            tenor = Decimal(str((maturity - cutoff_date).days / 365.25))

            if tenor <= 0:
                continue

            ns = curve_index[curve_id]["nelson_siegel"]

            curve_yield = nelson_siegel_zero_rate(
                tenor,
                beta0=Decimal(str(ns["beta0"])),
                beta1=Decimal(str(ns["beta1"])),
                beta2=Decimal(str(ns["beta2"])),
                tau=Decimal(str(ns["tau"])),
            )

            spread_bp = (weighted_market_yield - curve_yield) * Decimal("100")

            classification = self._classify(spread_bp)

            results.append(
                InstitutionalRelativeValueResult(
                    curve_id=curve_id,
                    isin=isin,
                    series=series,
                    issuer=meta["issuer"],
                    currency=meta["currency"],
                    product_code=meta["product_code"],
                    maturity_date=maturity,
                    tenor=tenor,
                    position_count=len(grouped_positions),
                    market_value_crc=total_market_value,
                    market_yield=weighted_market_yield,
                    curve_yield=curve_yield,
                    spread_bp=spread_bp,
                    classification=classification,
                )
            )

        return tuple(
            sorted(
                results,
                key=lambda item: item.spread_bp,
                reverse=True,
            )
        )

    def _resolve_curve_id(
        self,
        position: dict[str, Any],
    ) -> str | None:
        issuer = str(position.get("issuer", "")).strip().upper()
        currency = str(position.get("currency", "")).strip().upper()
        product_code = str(position.get("product_code", "")).strip().lower()

        return self._CURVE_MAPPING.get((issuer, currency, product_code))

    def _classify(self, spread_bp: Decimal) -> str:
        if spread_bp > self.CHEAP_THRESHOLD_BP:
            return "CHEAP"

        if spread_bp < self.RICH_THRESHOLD_BP:
            return "RICH"

        return "NEUTRAL"
