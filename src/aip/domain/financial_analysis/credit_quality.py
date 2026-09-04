from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation
from enum import Enum


class CreditAgingBand(str, Enum):
    """Bandas de atraso normalizadas para cálculo de calidad de cartera."""

    CURRENT = "CURRENT"
    DAYS_1_30 = "DAYS_1_30"
    DAYS_31_60 = "DAYS_31_60"
    DAYS_61_90 = "DAYS_61_90"
    DAYS_91_180 = "DAYS_91_180"
    DAYS_181_PLUS = "DAYS_181_PLUS"
    JUDICIAL_COLLECTION = "JUDICIAL_COLLECTION"


@dataclass(frozen=True, slots=True)
class CreditAgingAmount:
    band: CreditAgingBand
    principal: Decimal


@dataclass(frozen=True, slots=True)
class CreditQualityCalculation:
    """Resultado de indicadores 08ME14-01 derivados de bandas de atraso."""

    gross_direct_portfolio: Decimal | None
    current_portfolio: Decimal | None
    delinquency_over_90: Decimal | None
    complete: bool
    missing_bands: tuple[CreditAgingBand, ...] = ()


class CreditQualityIndicatorCalculator:
    """Calcula calidad de cartera sin depender de SUGEF, archivos o UI.

    Fórmulas institucionales 08ME14-01:

    * Cartera de crédito al día = cartera al día / cartera de crédito bruta.
    * Morosidad >90 días = cartera con atraso >90 días y cobro judicial /
      cartera directa.

    El adaptador de infraestructura es responsable de traducir las categorías
    de la fuente a ``CreditAgingBand``. Para evitar convertir ausencia de datos
    en cero, el cálculo exige las siete bandas. Si una banda no fue publicada o
    no pudo leerse, ambos indicadores quedan no disponibles.
    """

    _ALL_BANDS = tuple(CreditAgingBand)
    _OVER_90 = (
        CreditAgingBand.DAYS_91_180,
        CreditAgingBand.DAYS_181_PLUS,
        CreditAgingBand.JUDICIAL_COLLECTION,
    )

    def calculate(
        self,
        amounts: tuple[CreditAgingAmount, ...],
    ) -> CreditQualityCalculation:
        by_band: dict[CreditAgingBand, Decimal] = {}
        for item in amounts:
            by_band[item.band] = by_band.get(item.band, Decimal("0")) + item.principal

        missing = tuple(band for band in self._ALL_BANDS if band not in by_band)
        if missing:
            return CreditQualityCalculation(
                gross_direct_portfolio=None,
                current_portfolio=None,
                delinquency_over_90=None,
                complete=False,
                missing_bands=missing,
            )

        gross = sum(by_band.values(), start=Decimal("0"))
        if gross == Decimal("0"):
            return CreditQualityCalculation(
                gross_direct_portfolio=gross,
                current_portfolio=None,
                delinquency_over_90=None,
                complete=False,
            )

        current = self._ratio(by_band[CreditAgingBand.CURRENT], gross)
        overdue = sum((by_band[band] for band in self._OVER_90), start=Decimal("0"))
        delinquency = self._ratio(overdue, gross)
        return CreditQualityCalculation(
            gross_direct_portfolio=gross,
            current_portfolio=current,
            delinquency_over_90=delinquency,
            complete=current is not None and delinquency is not None,
        )

    @staticmethod
    def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
        if denominator == Decimal("0"):
            return None
        try:
            return numerator / denominator
        except (DivisionByZero, InvalidOperation):
            return None
