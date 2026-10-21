"""Reproduce the August-2026 Excel 08ME14-01 valuation independently.

The reference is the workbook "Matriz Evaluacion Indicadores AGOSTO 2026 2":
P15/P85 inclusive interpolation; the lower ROA/ROE cutoff is floored at zero;
three profitability weights are 6.67 points, not 20/3; classification uses the
maximum completed entity score in the SAME cohort and month.

This module never silently awards liquidity points on missing data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Mapping

from aip.domain.financial_analysis.models import RatingDirection, RatingLevel
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService

_FOUR_DP = Decimal("0.0001")
_MIN_PEERS = 3
_PROFITABILITY = frozenset({"MARGIN_INTERMEDIATION", "ROA", "ROE"})
_FLOORED_LOWER = frozenset({"ROA", "ROE"})
_BINARY = frozenset({"PROPORTIONAL_SUPERVISION", "STATE_GUARANTEE"})
_FACTORS = {
    RatingLevel.OUTSTANDING: Decimal("1"),
    RatingLevel.SATISFACTORY: Decimal("0.75"),
    RatingLevel.IMPROVABLE: Decimal("0.50"),
    RatingLevel.CRITICAL: Decimal("0.25"),
}


@dataclass(frozen=True, slots=True)
class MatrixEntityInput:
    entity_id: str
    name: str
    indicators: Mapping[str, Decimal | None]
    regulation_full: bool | None
    state_guarantee: bool | None


@dataclass(frozen=True, slots=True)
class MatrixIndicatorResult:
    code: str
    value: Decimal | None
    p15: Decimal | None
    midpoint: Decimal | None
    p85: Decimal | None
    level: RatingLevel
    weight: Decimal
    contribution: Decimal | None
    origin: str


@dataclass(frozen=True, slots=True)
class MatrixEntityResult:
    entity_id: str
    name: str
    score: Decimal | None
    grade: str | None
    status: str
    indicators: tuple[MatrixIndicatorResult, ...]
    missing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MatrixCohortResult:
    entities: tuple[MatrixEntityResult, ...]
    score_maximum: Decimal | None
    peer_counts: Mapping[str, int]
    lower_cutoffs: Mapping[str, Decimal | None]
    upper_cutoffs: Mapping[str, Decimal | None]
    incomplete_entities: tuple[str, ...]


class MatrixReferenceRatingService:
    """Reference-compatible results for a single explicit, same-cutoff peer universe."""

    @staticmethod
    def _percentile(values: tuple[Decimal, ...], q: Decimal) -> Decimal:
        return FinancialEntityRatingService._percentile(values, q)

    @classmethod
    def evaluate(
        cls,
        entities: tuple[MatrixEntityInput, ...],
        *,
        documented_liquidity_exceptions: frozenset[str] = frozenset(),
    ) -> MatrixCohortResult:
        """Evaluate one period; overrides require explicit named entity IDs.

        The override only exists to reproduce the source workbook's five
        blank-but-fully-scored liquidity cells for audit purposes; never use it
        on production SUGEF records without separately documented approval.
        """
        if len({entity.entity_id for entity in entities}) != len(entities):
            raise ValueError("La cohorte tiene identificadores de entidad duplicados.")
        identifiers = {entity.entity_id for entity in entities}
        if documented_liquidity_exceptions - identifiers:
            raise ValueError("Excepción de liquidez ajena a la cohorte.")

        definitions = FinancialEntityRatingService.INDICATORS
        cutoffs: dict[str, tuple[Decimal, Decimal, Decimal] | None] = {}
        peer_counts: dict[str, int] = {}
        for definition in definitions:
            if definition.code in _BINARY:
                continue
            values = tuple(
                value
                for entity in entities
                if (value := entity.indicators.get(definition.code)) is not None
            )
            peer_counts[definition.code] = len(values)
            if len(values) < _MIN_PEERS:
                cutoffs[definition.code] = None
                continue
            lower = cls._percentile(values, Decimal("0.15"))
            upper = cls._percentile(values, Decimal("0.85"))
            if definition.code in _FLOORED_LOWER:
                lower = max(lower, Decimal("0"))
            mid = (lower + upper) / Decimal("2")
            cutoffs[definition.code] = (lower, mid, upper)

        output: list[MatrixEntityResult] = []
        for entity in entities:
            measures: list[MatrixIndicatorResult] = []
            for definition in definitions:
                code = definition.code
                weight = (
                    Decimal("6.67")
                    if code in _PROFITABILITY
                    else definition.weight_percent
                )
                cutoff = cutoffs.get(code)
                level = RatingLevel.UNAVAILABLE
                origin = "DATOS_SUGEF"
                contribution = None
                value = entity.indicators.get(code)
                if code == "PROPORTIONAL_SUPERVISION":
                    value = (
                        Decimal("1") if entity.regulation_full else Decimal("0")
                    ) if entity.regulation_full is not None else None
                    if value is not None:
                        contribution = weight if value == Decimal("1") else Decimal("0")
                elif code == "STATE_GUARANTEE":
                    value = (
                        Decimal("1") if entity.state_guarantee else Decimal("0")
                    ) if entity.state_guarantee is not None else None
                    if value is not None:
                        contribution = weight if value == Decimal("1") else Decimal("0")
                elif cutoff is not None and value is not None:
                    lower, mid, upper = cutoff
                    level = FinancialEntityRatingService._level(
                        value, lower, mid, upper, definition.direction
                    )
                    contribution = weight * _FACTORS[level]
                elif (
                    code == "LIQUIDITY_COVERAGE"
                    and entity.entity_id in documented_liquidity_exceptions
                    and value is None
                ):
                    contribution = weight
                    origin = "EXCEPCION_EXCEL_DOCUMENTADA"
                if code in _BINARY and contribution is not None:
                    level = (
                        RatingLevel.OUTSTANDING
                        if contribution == weight
                        else RatingLevel.CRITICAL
                    )
                    origin = "CATALOGO_INSTITUCIONAL"
                measures.append(
                    MatrixIndicatorResult(
                        code=code, value=value,
                        p15=cutoff[0] if cutoff is not None else None,
                        midpoint=cutoff[1] if cutoff is not None else None,
                        p85=cutoff[2] if cutoff is not None else None,
                        level=level, weight=weight, contribution=contribution,
                        origin=origin,
                    )
                )
            missing = tuple(
                measure.code for measure in measures
                if measure.contribution is None
            )
            score = (
                sum(
                    (measure.contribution for measure in measures
                     if measure.contribution is not None),
                    start=Decimal("0"),
                ).quantize(_FOUR_DP)
                if not missing else None
            )
            output.append(
                MatrixEntityResult(
                    entity_id=entity.entity_id,
                    name=entity.name,
                    score=score,
                    grade=None,
                    status="COMPLETE" if score is not None else "INCOMPLETE",
                    indicators=tuple(measures),
                    missing=missing,
                )
            )
        maximum = max(
            (item.score for item in output if item.score is not None),
            default=None,
        )
        completed = tuple(
            replace(item, grade=cls.grade(item.score, maximum))
            if item.score is not None and maximum is not None else item
            for item in output
        )
        return MatrixCohortResult(
            entities=completed,
            score_maximum=maximum,
            peer_counts=peer_counts,
            lower_cutoffs={
                code: values[0] if values is not None else None
                for code, values in cutoffs.items()
            },
            upper_cutoffs={
                code: values[2] if values is not None else None
                for code, values in cutoffs.items()
            },
            incomplete_entities=tuple(
                item.entity_id for item in completed if item.score is None
            ),
        )

    @staticmethod
    def grade(score: Decimal, maximum: Decimal) -> str:
        if maximum <= Decimal("0"):
            raise ValueError("La nota máxima de la cohorte debe ser positiva.")
        if score >= maximum * Decimal("0.85"):
            return "AA"
        if score >= maximum * Decimal("0.75"):
            return "A"
        if score >= maximum * Decimal("0.65"):
            return "BB"
        if score >= maximum * Decimal("0.55"):
            return "B"
        return "CC"
