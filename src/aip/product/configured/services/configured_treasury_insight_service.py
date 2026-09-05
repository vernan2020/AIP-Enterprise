from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class TreasuryInsightItem:
    title: str
    detail: str
    severity: str
    source: str


@dataclass(frozen=True, slots=True)
class TreasuryInsightResult:
    alerts: tuple[TreasuryInsightItem, ...]
    observations: tuple[TreasuryInsightItem, ...]
    opportunities: tuple[TreasuryInsightItem, ...]


class ConfiguredTreasuryInsightService:
    """Construye señales auditables de tesorería desde resultados certificados."""

    _STATUS_TRANSLATIONS = {
        "SCREENING": "PRESELECCIÓN",
        "PASS": "CUMPLE",
        "FAIL": "NO CUMPLE",
        "AVAILABLE": "DISPONIBLE",
        "UNAVAILABLE": "NO DISPONIBLE",
    }

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None or value == "":
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _format_crc_mm(value: Decimal) -> str:
        return f"₡{value / Decimal('1000000'):,.2f} MM"

    @classmethod
    def build(
        cls,
        *,
        liquidity: dict[str, Any],
        market: dict[str, Any] | None = None,
    ) -> TreasuryInsightResult:
        alerts: list[TreasuryInsightItem] = []
        observations: list[TreasuryInsightItem] = []
        opportunities: list[TreasuryInsightItem] = []

        liquidity_gap = cls._decimal(liquidity.get("liquidity_gap"))
        hqla_capacity = cls._decimal(liquidity.get("hqla_capacity"))
        mil_capacity = cls._decimal(liquidity.get("mil_eligible_capacity"))
        maturity_30d = cls._decimal(liquidity.get("maturity_30d_crc"))

        if liquidity_gap < 0:
            alerts.append(
                TreasuryInsightItem(
                    title="Brecha de liquidez negativa",
                    detail=f"Brecha calculada: {cls._format_crc_mm(liquidity_gap)}.",
                    severity="Alta",
                    source="Motor de Liquidez",
                )
            )

        observations.append(
            TreasuryInsightItem(
                title="Capacidad líquida disponible",
                detail=(
                    f"HQLA {cls._format_crc_mm(hqla_capacity)} · "
                    f"MIL {cls._format_crc_mm(mil_capacity)}."
                ),
                severity="Informativa",
                source="Motor de Liquidez",
            )
        )

        if maturity_30d > 0:
            alerts.append(
                TreasuryInsightItem(
                    title="Vencimientos próximos",
                    detail=(
                        "Valor de mercado con vencimiento contractual ≤30 días: "
                        f"{cls._format_crc_mm(maturity_30d)}."
                    ),
                    severity="Informativa",
                    source="Motor de Vencimientos del Portafolio",
                )
            )

        if market is not None:
            rotations = [
                item
                for item in market.get("portfolio_rotation_results", ())
                if isinstance(item, dict)
            ]
            ranked: list[tuple[Decimal, dict[str, Any]]] = []
            for item in rotations:
                pickup = cls._decimal(
                    item.get("spread_pickup_bp", item.get("spread_improvement_bp"))
                )
                if pickup > 0:
                    ranked.append((pickup, item))
            ranked.sort(key=lambda pair: pair[0], reverse=True)
            for pickup, item in ranked[:5]:
                source_series = str(item.get("source_series") or "Origen")
                target_series = str(item.get("target_series") or "Destino")
                raw_status = str(item.get("screening_status") or "SCREENING").upper()
                status = cls._STATUS_TRANSLATIONS.get(raw_status, raw_status)
                opportunities.append(
                    TreasuryInsightItem(
                        title=f"Rotación {source_series} → {target_series}",
                        detail=f"Mejora preliminar del diferencial: {pickup:+.1f} pb · {status}.",
                        severity="Oportunidad",
                        source="Motor de Valor Relativo",
                    )
                )

        return TreasuryInsightResult(
            alerts=tuple(alerts),
            observations=tuple(observations),
            opportunities=tuple(opportunities),
        )
