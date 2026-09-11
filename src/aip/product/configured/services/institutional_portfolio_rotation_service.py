from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InstitutionalPortfolioRotationResult:
    """Preliminary relative-value rotation screening result.

    This object is deliberately not a trade recommendation.  It identifies a
    same-curve source/target pair whose relative-value spread merits review and
    keeps the portfolio-risk reviews explicit for the downstream treasury
    decision layer.
    """

    source_series: str
    source_issuer: str
    source_currency: str
    source_curve_id: str
    source_spread_bp: float
    source_market_yield: float
    source_curve_yield: float
    source_tenor: float
    source_market_value_crc: float

    target_series: str
    target_issuer: str
    target_currency: str
    target_curve_id: str
    target_spread_bp: float
    target_market_yield: float
    target_curve_yield: float
    target_tenor: float
    target_market_price: float | None
    target_in_portfolio: bool

    spread_improvement_bp: float
    yield_improvement_bp: float
    tenor_difference_years: float

    rotation_score: float
    screening_status: str
    signal_type: str
    requires_duration_review: bool
    requires_liquidity_review: bool
    requires_concentration_review: bool
    explanation: str


class InstitutionalPortfolioRotationService:
    """Screen portfolio rotations from institutional relative-value signals.

    Governance rules implemented here are intentionally narrow:

    * the source must be rich/expensive versus its institutional curve;
    * the target must be cheap versus the same institutional curve;
    * source and target must be different securities;
    * no duration, liquidity or issuer-limit conclusion is inferred from
      relative value alone; those reviews remain mandatory.

    The service therefore produces candidates for analysis, never executable
    trade instructions.
    """

    CANDIDATE_MIN_SPREAD_IMPROVEMENT_BP = 20.0

    _RICH_CLASSIFICATIONS = frozenset({"RICH", "CARO"})
    _CHEAP_CLASSIFICATIONS = frozenset({"CHEAP", "BARATO"})

    def calculate(
        self,
        portfolio_relative_value: list[dict[str, Any]],
        market_relative_value: list[dict[str, Any]],
    ) -> tuple[InstitutionalPortfolioRotationResult, ...]:
        sources = [
            normalized
            for item in portfolio_relative_value
            if (normalized := self._normalize_source(item)) is not None
        ]
        targets = [
            normalized
            for item in market_relative_value
            if (normalized := self._normalize_target(item)) is not None
        ]

        results: list[InstitutionalPortfolioRotationResult] = []
        for source in sources:
            for target in targets:
                if target["curve_id"] != source["curve_id"]:
                    continue
                if target["series"].upper() == source["series"].upper():
                    continue

                spread_improvement = target["spread_bp"] - source["spread_bp"]
                if spread_improvement <= 0.0:
                    continue

                yield_improvement = (target["market_yield"] - source["market_yield"]) * 100.0
                tenor_difference = target["tenor"] - source["tenor"]

                status = self._screening_status(
                    spread_improvement_bp=spread_improvement,
                    target_in_portfolio=target["in_portfolio"],
                )

                results.append(
                    InstitutionalPortfolioRotationResult(
                        source_series=source["series"],
                        source_issuer=source["issuer"],
                        source_currency=source["currency"],
                        source_curve_id=source["curve_id"],
                        source_spread_bp=source["spread_bp"],
                        source_market_yield=source["market_yield"],
                        source_curve_yield=source["curve_yield"],
                        source_tenor=source["tenor"],
                        source_market_value_crc=source["market_value_crc"],
                        target_series=target["series"],
                        target_issuer=target["issuer"],
                        target_currency=source["currency"],
                        target_curve_id=target["curve_id"],
                        target_spread_bp=target["spread_bp"],
                        target_market_yield=target["market_yield"],
                        target_curve_yield=target["curve_yield"],
                        target_tenor=target["tenor"],
                        target_market_price=target["market_price"],
                        target_in_portfolio=target["in_portfolio"],
                        spread_improvement_bp=spread_improvement,
                        yield_improvement_bp=yield_improvement,
                        tenor_difference_years=tenor_difference,
                        rotation_score=spread_improvement,
                        screening_status=status,
                        signal_type="RELATIVE_VALUE_ROTATION",
                        requires_duration_review=True,
                        requires_liquidity_review=True,
                        requires_concentration_review=True,
                        explanation=self._explanation(
                            source_series=source["series"],
                            target_series=target["series"],
                            spread_improvement_bp=spread_improvement,
                            target_in_portfolio=target["in_portfolio"],
                            status=status,
                        ),
                    )
                )

        return tuple(
            sorted(
                results,
                key=lambda item: (
                    item.screening_status != "CANDIDATO",
                    -item.rotation_score,
                    item.source_series,
                    item.target_series,
                ),
            )
        )

    def _normalize_source(self, item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        classification = str(item.get("classification") or "").strip().upper()
        if classification not in self._RICH_CLASSIFICATIONS:
            return None

        series = str(item.get("series") or item.get("instrument") or "").strip()
        issuer = str(item.get("issuer") or "").strip()
        currency = str(item.get("currency") or "").strip()
        curve_id = str(item.get("curve_id") or "").strip()
        if not series or not curve_id:
            return None

        values = self._numeric_values(
            item,
            (
                "spread_bp",
                "market_yield",
                "curve_yield",
                "tenor",
                "market_value_crc",
            ),
        )
        if values is None or values["market_value_crc"] <= 0.0:
            return None

        return {
            "series": series,
            "issuer": issuer,
            "currency": currency,
            "curve_id": curve_id,
            **values,
        }

    def _normalize_target(self, item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        classification = str(item.get("classification") or "").strip().upper()
        if classification not in self._CHEAP_CLASSIFICATIONS:
            return None

        series = str(item.get("series") or "").strip()
        issuer = str(item.get("issuer") or "").strip()
        curve_id = str(item.get("curve_id") or "").strip()
        if not series or not curve_id:
            return None

        values = self._numeric_values(
            item,
            ("spread_bp", "market_yield", "curve_yield", "tenor"),
        )
        if values is None:
            return None

        market_price_raw = item.get("market_price")
        try:
            market_price = float(market_price_raw) if market_price_raw is not None else None
        except (TypeError, ValueError):
            market_price = None

        return {
            "series": series,
            "issuer": issuer,
            "curve_id": curve_id,
            "market_price": market_price,
            "in_portfolio": bool(item.get("in_portfolio", False)),
            **values,
        }

    @staticmethod
    def _numeric_values(
        item: dict[str, Any],
        names: tuple[str, ...],
    ) -> dict[str, float] | None:
        values: dict[str, float] = {}
        try:
            for name in names:
                raw = item.get(name)
                if raw is None:
                    return None
                values[name] = float(raw)
        except (TypeError, ValueError):
            return None
        return values

    def _screening_status(
        self,
        *,
        spread_improvement_bp: float,
        target_in_portfolio: bool,
    ) -> str:
        if (
            spread_improvement_bp >= self.CANDIDATE_MIN_SPREAD_IMPROVEMENT_BP
            and not target_in_portfolio
        ):
            return "CANDIDATO"
        return "REVISAR"

    @staticmethod
    def _explanation(
        *,
        source_series: str,
        target_series: str,
        spread_improvement_bp: float,
        target_in_portfolio: bool,
        status: str,
    ) -> str:
        target_state = (
            "el destino ya está presente en el portafolio"
            if target_in_portfolio
            else "el destino está fuera del portafolio"
        )
        return (
            f"Screening {status}: {source_series} -> {target_series}; "
            f"mejora relativa {spread_improvement_bp:.2f} pb y {target_state}. "
            "Requiere validar duración, liquidez y concentración antes de cualquier decisión."
        )
