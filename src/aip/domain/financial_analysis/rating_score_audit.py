"""Auditoría independiente de la puntuación 08ME14-01 V01.

No recalcula indicadores financieros ni modifica el motor certificado. Contrasta
valores, bandas, niveles, ponderaciones, sumas y escala; ofrece una sensibilidad
NO normativa sobre la codificación ambigua de supervisión proporcional.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    EntityFinancialRating,
    RatingDirection,
    RatingLevel,
)
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService

_FACTORS: dict[RatingLevel, Decimal] = {
    RatingLevel.OUTSTANDING: Decimal("1"),
    RatingLevel.SATISFACTORY: Decimal("0.75"),
    RatingLevel.IMPROVABLE: Decimal("0.50"),
    RatingLevel.CRITICAL: Decimal("0.25"),
}
_POINTS = {
    RatingLevel.OUTSTANDING: 4,
    RatingLevel.SATISFACTORY: 3,
    RatingLevel.IMPROVABLE: 2,
    RatingLevel.CRITICAL: 1,
}
_THOUSANDTH = Decimal("0.001")


@dataclass(frozen=True, slots=True)
class ScoreAuditIndicator:
    code: str
    label: str
    dimension: str
    value: Decimal | None
    direction: RatingDirection
    p15: Decimal | None
    midpoint: Decimal | None
    p85: Decimal | None
    level: RatingLevel
    expected_level: RatingLevel
    points: int | None
    weight: Decimal
    factor: Decimal | None
    expected: Decimal | None
    reported: Decimal | None
    difference: Decimal | None
    status: str
    rule: str
    source: str


@dataclass(frozen=True, slots=True)
class ScoreAuditResult:
    rows: tuple[ScoreAuditIndicator, ...]
    status: str
    recomputed_score: Decimal | None
    reported_score: Decimal | None
    reported_grade: str | None
    recomputed_grade: str | None
    issues: tuple[str, ...]
    criterion_warning: str


class RatingScoreAuditService:
    """Audita la nota usando las definiciones vigentes, sin escribir valores."""

    CRITERION_WARNING = (
        "Conciliación de codificación: la matriz de referencia representa "
        "1=regulación plena y 0=proporcional; AIP representa 0=no aplica "
        "supervisión proporcional y 1=sí aplica. El significado económico "
        "y los 5 puntos coinciden cuando el catálogo institucional es correcto. "
        "Revisar la fuente binaria para cada entidad."
    )

    @classmethod
    def audit(cls, rating: EntityFinancialRating) -> ScoreAuditResult:
        definitions = {item.code: item for item in FinancialEntityRatingService.INDICATORS}
        rows: list[ScoreAuditIndicator] = []
        issues: list[str] = []
        observed: set[str] = set()

        for item in rating.indicators:
            if item.code in observed:
                issues.append(f"Indicador duplicado: {item.code}.")
            observed.add(item.code)
            definition = definitions.get(item.code)
            if definition is None:
                issues.append(f"Indicador ajeno a la metodología: {item.code}.")
            elif (
                item.weight_percent != definition.weight_percent
                or item.dimension != definition.dimension
                or item.direction != definition.direction
            ):
                issues.append(f"Definición o peso alterado: {item.label}.")
            expected_level, factor, rule = cls._recalculate(item, definition)
            expected = item.weight_percent * factor if factor is not None else None
            difference = (
                item.contribution - expected
                if expected is not None and item.contribution is not None
                else None
            )
            status = "CUADRA"
            if expected_level is RatingLevel.UNAVAILABLE:
                status = "SIN INSUMOS"
            elif expected_level != item.level or difference != Decimal("0"):
                status = "REVISAR"
                issues.append(f"{item.label}: nivel o aporte distinto del recalculado.")
            points = (
                (1 if factor == Decimal("1") else 0)
                if item.direction is RatingDirection.BINARY and factor is not None
                else _POINTS.get(expected_level)
            )
            rows.append(
                ScoreAuditIndicator(
                    code=item.code,
                    label=item.label,
                    dimension=item.dimension,
                    value=item.value,
                    direction=item.direction,
                    p15=item.percentile_15,
                    midpoint=item.midpoint,
                    p85=item.percentile_85,
                    level=item.level,
                    expected_level=expected_level,
                    points=points,
                    weight=item.weight_percent,
                    factor=factor,
                    expected=expected,
                    reported=item.contribution,
                    difference=difference,
                    status=status,
                    rule=rule,
                    source=item.source_account or "",
                )
            )

        if observed != set(definitions):
            issues.append("Universo de indicadores diferente de los 13 definidos.")
        for dimension in rating.dimensions:
            recomputed_dimension = sum(
                (row.expected or Decimal("0") for row in rows if row.dimension == dimension.name),
                start=Decimal("0"),
            ).quantize(_THOUSANDTH)
            if dimension.score != recomputed_dimension:
                issues.append(f"Dimensión {dimension.name}: suma no coincide.")

        complete = (
            rating.status == "COMPLETE"
            and len(rows) == len(definitions)
            and all(row.expected is not None for row in rows)
        )
        recomputed = (
            sum(
                (row.expected for row in rows if row.expected is not None), start=Decimal("0")
            ).quantize(_THOUSANDTH)
            if complete
            else None
        )
        recomputed_grade = (
            FinancialEntityRatingService.grade(recomputed) if recomputed is not None else None
        )
        if complete and (rating.score != recomputed or rating.grade != recomputed_grade):
            issues.append("Puntaje o categoría global difiere del valor reconstruido.")
        if not complete and (rating.score is not None or rating.grade is not None):
            issues.append("Se emitió nota sin los 13 aportes verificables.")

        return ScoreAuditResult(
            rows=tuple(rows),
            status="REVISAR" if issues else ("CUADRA" if complete else "INCOMPLETA"),
            recomputed_score=recomputed,
            reported_score=rating.score,
            reported_grade=rating.grade,
            recomputed_grade=recomputed_grade,
            issues=tuple(issues),
            criterion_warning=cls.CRITERION_WARNING,
        )

    @staticmethod
    def _recalculate(item, definition) -> tuple[RatingLevel, Decimal | None, str]:
        if item.direction is RatingDirection.BINARY:
            rule = (
                "Sin supervisión proporcional (0) = aporte completo."
                if item.code == "PROPORTIONAL_SUPERVISION"
                else "Garantía del Estado (1) = aporte completo."
            )
            if item.value not in (Decimal("0"), Decimal("1")) or definition is None:
                return RatingLevel.UNAVAILABLE, None, rule
            factor = (
                Decimal("1") if item.value == definition.binary_favorable_value else Decimal("0")
            )
            return (
                RatingLevel.OUTSTANDING if factor else RatingLevel.CRITICAL,
                factor,
                rule,
            )

        rule = (
            "P15 / punto medio / P85; mayor es mejor."
            if item.direction is RatingDirection.HIGHER_IS_BETTER
            else "P15 / punto medio / P85; menor es mejor."
        )
        if (
            item.value is None
            or item.percentile_15 is None
            or item.midpoint is None
            or item.percentile_85 is None
        ):
            return RatingLevel.UNAVAILABLE, None, rule
        value = item.value
        lower = item.percentile_15
        mid = item.midpoint
        upper = item.percentile_85
        if not lower <= mid <= upper:
            return RatingLevel.UNAVAILABLE, None, "Bandas no ordenadas; revisar pares."
        if item.direction is RatingDirection.HIGHER_IS_BETTER:
            level = (
                RatingLevel.OUTSTANDING
                if value > upper
                else (
                    RatingLevel.SATISFACTORY
                    if value > mid
                    else RatingLevel.IMPROVABLE if value > lower else RatingLevel.CRITICAL
                )
            )
        else:
            level = (
                RatingLevel.OUTSTANDING
                if value < lower
                else (
                    RatingLevel.SATISFACTORY
                    if value < mid
                    else RatingLevel.IMPROVABLE if value < upper else RatingLevel.CRITICAL
                )
            )
        return level, _FACTORS[level], rule
