from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.financial_math.curves.nelson_siegel import (
    nelson_siegel_zero_rate,
)


@dataclass(frozen=True, slots=True)
class InstitutionalMarketRelativeValueResult:
    """Resultado de valor relativo para un instrumento del mercado PiPCA."""

    curve_id: str
    issuer: str
    series: str
    isin: str
    maturity_date: date
    tenor: Decimal
    market_yield: Decimal
    curve_yield: Decimal
    spread_bp: Decimal
    classification: str
    market_price: Decimal | None
    in_portfolio: bool


class InstitutionalMarketRelativeValueService:
    """Analiza valor relativo del universo completo elegible del mercado."""

    CHEAP_THRESHOLD_BP = Decimal("10")
    RICH_THRESHOLD_BP = Decimal("-10")

    _CURVE_MAPPING = {
        ("G", "tp"): "GOBIERNO_CRC",
        ("G", "tp$"): "GOBIERNO_USD",
        ("BCCR", "bem"): "BCCR_CRC",
    }

    def calculate(
        self,
        vector_records: list[dict[str, Any]],
        curves: list[dict[str, Any]],
        cutoff_date: date,
        portfolio_positions: list[dict[str, Any]] | None = None,
    ) -> tuple[InstitutionalMarketRelativeValueResult, ...]:
        curve_index = {
            str(curve_id): curve
            for curve in curves
            if isinstance(curve, dict)
            and (curve_id := curve.get("curve_id"))
            and isinstance(curve.get("nelson_siegel"), dict)
        }

        portfolio_series = {
            str(position.get("series") or "")
            .strip()
            .upper()
            for position in (portfolio_positions or [])
            if position.get("series")
        }

        results: list[InstitutionalMarketRelativeValueResult] = []

        for record in vector_records:
            issuer = str(
                record.get("issuer", "")
            ).strip().upper()

            mnemonic = str(
                record.get(
                    "instrument_type_or_mnemonic",
                    "",
                )
            ).strip().lower()

            curve_id = self._CURVE_MAPPING.get(
                (issuer, mnemonic)
            )

            if curve_id is None:
                continue

            if curve_id not in curve_index:
                continue

            series = str(
                record.get(
                    "series_or_security_code",
                    "",
                )
            ).strip()

            if not series:
                continue

            maturity = record.get(
                "maturity_date_if_present"
            )

            market_yield_raw = record.get(
                "market_yield"
            )

            market_price_raw = record.get(
                "market_price"
            )

            isin = str(
                record.get(
                    "isin_if_present"
                )
                or ""
            ).strip()

            if maturity is None:
                continue

            if market_yield_raw is None:
                continue

            market_yield = Decimal(
                str(market_yield_raw)
            )

            if market_yield <= 0:
                continue

            tenor = Decimal(
                str(
                    (maturity - cutoff_date).days
                    / 365.25
                )
            )

            if tenor <= 0:
                continue

            ns = curve_index[
                curve_id
            ]["nelson_siegel"]

            curve_yield = nelson_siegel_zero_rate(
                tenor,
                beta0=Decimal(
                    str(ns["beta0"])
                ),
                beta1=Decimal(
                    str(ns["beta1"])
                ),
                beta2=Decimal(
                    str(ns["beta2"])
                ),
                tau=Decimal(
                    str(ns["tau"])
                ),
            )

            spread_bp = (
                market_yield
                - curve_yield
            ) * Decimal("100")

            classification = self._classify(
                spread_bp
            )

            market_price = (
                Decimal(str(market_price_raw))
                if market_price_raw is not None
                else None
            )

            in_portfolio = (
                series.upper()
                in portfolio_series
            )

            results.append(
                InstitutionalMarketRelativeValueResult(
                    curve_id=curve_id,
                    issuer=issuer,
                    series=series,
                    isin=isin,
                    maturity_date=maturity,
                    tenor=tenor,
                    market_yield=market_yield,
                    curve_yield=curve_yield,
                    spread_bp=spread_bp,
                    classification=classification,
                    market_price=market_price,
                    in_portfolio=in_portfolio,
                )
            )

        return tuple(
            sorted(
                results,
                key=lambda item: item.spread_bp,
                reverse=True,
            )
        )

    def _classify(
        self,
        spread_bp: Decimal,
    ) -> str:
        if spread_bp > self.CHEAP_THRESHOLD_BP:
            return "BARATO"

        if spread_bp < self.RICH_THRESHOLD_BP:
            return "CARO"

        return "NEUTRAL"
