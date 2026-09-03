from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    EntityFinancialRating,
    FinancialStatementLine,
    RatingDimensionAssessment,
    RatingDirection,
    RatingIndicatorAssessment,
    RatingLevel,
)


@dataclass(frozen=True, slots=True)
class RatingIndicatorDefinition:
    code: str
    label: str
    dimension: str
    weight_percent: Decimal
    direction: RatingDirection
    aliases: tuple[str, ...]


class FinancialEntityRatingService:
    """Ejecuta 08ME14-01 V01 sin depender de Excel, archivos ni Qt."""

    METHODOLOGY_CODE = "08ME14-01"
    METHODOLOGY_VERSION = "V01 · rige 27/06/2025"
    MINIMUM_PEERS = 3
    INDICATORS = (
        RatingIndicatorDefinition(
            "MARGIN_INTERMEDIATION",
            "Margen de Intermediación Financiera",
            "Rentabilidad",
            Decimal("20") / Decimal("3"),
            RatingDirection.HIGHER_IS_BETTER,
            ("MARGEN DE INTERMEDIACION FINANCIERA", "MARGEN DE INTERM FINANCIERA"),
        ),
        RatingIndicatorDefinition(
            "ROA",
            "ROA",
            "Rentabilidad",
            Decimal("20") / Decimal("3"),
            RatingDirection.HIGHER_IS_BETTER,
            ("ROA", "RETURN ON ASSETS", "RENDIMIENTO SOBRE ACTIVOS"),
        ),
        RatingIndicatorDefinition(
            "ROE",
            "ROE",
            "Rentabilidad",
            Decimal("20") / Decimal("3"),
            RatingDirection.HIGHER_IS_BETTER,
            ("ROE", "RETURN ON EQUITY", "RENDIMIENTO SOBRE PATRIMONIO"),
        ),
        RatingIndicatorDefinition(
            "CURRENT_PORTFOLIO",
            "Cartera de crédito al día",
            "Calidad de la Cartera",
            Decimal("10"),
            RatingDirection.HIGHER_IS_BETTER,
            ("CARTERA DE CREDITO AL DIA",),
        ),
        RatingIndicatorDefinition(
            "COVERAGE_ARREARS",
            "Cobertura de cartera en atraso",
            "Calidad de la Cartera",
            Decimal("5"),
            RatingDirection.HIGHER_IS_BETTER,
            ("COBERTURA DE CARTERA EN ATRASO", "COBERTURA DE CREDITO AL DIA"),
        ),
        RatingIndicatorDefinition(
            "DELINQUENCY_90",
            "Morosidad >90 días y cobro judicial / Cartera directa",
            "Calidad de la Cartera",
            Decimal("10"),
            RatingDirection.LOWER_IS_BETTER,
            (
                "MOROSIDAD >90 DIAS Y COBRO JUDICIAL / CARTERA DIRECTA",
                "MOROSIDAD >90D Y COBRO JUDICIAL / CARTERA DIRECTA",
                "MOROSIDAD >90 DIAS",
            ),
        ),
        RatingIndicatorDefinition(
            "OPERATING_EFFICIENCY",
            "Eficiencia Operativa",
            "Desempeño Operativo",
            Decimal("7.5"),
            RatingDirection.LOWER_IS_BETTER,
            ("EFICIENCIA OPERATIVA",),
        ),
        RatingIndicatorDefinition(
            "ADMIN_EXPENSE_ASSETS",
            "Gasto Administrativo sobre Activos",
            "Desempeño Operativo",
            Decimal("7.5"),
            RatingDirection.LOWER_IS_BETTER,
            ("GASTO ADMINISTRATIVO SOBRE ACTIVOS",),
        ),
        RatingIndicatorDefinition(
            "EQUITY_COMMITMENT",
            "Compromiso Patrimonial",
            "Solvencia",
            Decimal("10"),
            RatingDirection.LOWER_IS_BETTER,
            ("COMPROMISO PATRIMONIAL",),
        ),
        RatingIndicatorDefinition(
            "CAPITAL_ADEQUACY",
            "Suficiencia Patrimonial",
            "Solvencia",
            Decimal("10"),
            RatingDirection.HIGHER_IS_BETTER,
            ("SUFICIENCIA PATRIMONIAL",),
        ),
        RatingIndicatorDefinition(
            "LIQUIDITY_COVERAGE",
            "Disponibilidades e Inversiones Disponibles / Obligaciones con el público",
            "Liquidez",
            Decimal("10"),
            RatingDirection.HIGHER_IS_BETTER,
            (
                "DISPONIBILIDADES E INVERSIONES DISPONIBLES / OBLIGACIONES PUBLICO",
                "DISPONIBILIDADES E INVERSIONES DISPONIBLES SOBRE OBLIGACIONES CON EL PUBLICO",
            ),
        ),
        RatingIndicatorDefinition(
            "PROPORTIONAL_SUPERVISION",
            "Aplica Supervisión Proporcional",
            "Supervisión proporcional",
            Decimal("5"),
            RatingDirection.BINARY,
            ("APLICA SUPERVISION PROPORCIONAL",),
        ),
        RatingIndicatorDefinition(
            "STATE_GUARANTEE",
            "Garantía del Estado",
            "Supervisión proporcional",
            Decimal("5"),
            RatingDirection.BINARY,
            ("GARANTIA DEL ESTADO", "APLICA GARANTIA DEL ESTADO"),
        ),
    )
    DIMENSION_WEIGHTS = (
        ("Rentabilidad", Decimal("20")),
        ("Calidad de la Cartera", Decimal("25")),
        ("Desempeño Operativo", Decimal("15")),
        ("Solvencia", Decimal("20")),
        ("Liquidez", Decimal("10")),
        ("Supervisión proporcional", Decimal("10")),
    )

    def evaluate(
        self,
        lines: tuple[FinancialStatementLine, ...],
        *,
        selected_entity_id: str,
        cutoff_date: date,
    ) -> EntityFinancialRating:
        current = tuple(line for line in lines if line.statement_date == cutoff_date)
        by_entity: dict[str, list[FinancialStatementLine]] = defaultdict(list)
        for line in current:
            by_entity[line.entity.entity_id].append(line)

        assessments: list[RatingIndicatorAssessment] = []
        diagnostics: list[str] = []
        for definition in self.INDICATORS:
            selected_line = self._find_indicator(
                tuple(by_entity.get(selected_entity_id, ())), definition
            )
            assessment = self._assess(definition, selected_line, by_entity)
            assessments.append(assessment)
            if assessment.value is None:
                diagnostics.append(f"Falta el indicador: {definition.label}.")
            elif assessment.contribution is None:
                diagnostics.append(
                    f"{definition.label}: se requieren al menos "
                    f"{self.MINIMUM_PEERS} entidades comparables."
                )

        dimensions = self._dimensions(tuple(assessments))
        available = sum(item.contribution is not None for item in assessments)
        coverage = (Decimal(available) / Decimal(len(self.INDICATORS)) * Decimal("100")).quantize(
            Decimal("0.01")
        )
        complete = available == len(self.INDICATORS)
        score = None
        grade = None
        if complete:
            score = sum(
                (item.contribution or Decimal("0") for item in assessments),
                start=Decimal("0"),
            ).quantize(Decimal("0.001"))
            grade = self.grade(score)
        else:
            diagnostics.insert(
                0,
                "Calificación no emitida: la metodología oficial exige los 13 indicadores.",
            )
        return EntityFinancialRating(
            status="COMPLETE" if complete else "INCOMPLETE",
            methodology_code=self.METHODOLOGY_CODE,
            methodology_version=self.METHODOLOGY_VERSION,
            effective_date=cutoff_date,
            score=score,
            grade=grade,
            coverage_percent=coverage,
            indicators=tuple(assessments),
            dimensions=dimensions,
            diagnostics=tuple(diagnostics),
        )

    @classmethod
    def _assess(
        cls,
        definition: RatingIndicatorDefinition,
        selected_line: FinancialStatementLine | None,
        by_entity: dict[str, list[FinancialStatementLine]],
    ) -> RatingIndicatorAssessment:
        value = selected_line.amount if selected_line is not None else None
        source_account = None
        if selected_line is not None:
            source_account = selected_line.account_code or selected_line.account_name
        if definition.direction is RatingDirection.BINARY:
            if value not in {Decimal("0"), Decimal("1")}:
                value = None
            level = (
                RatingLevel.OUTSTANDING
                if value == Decimal("1")
                else RatingLevel.CRITICAL if value == Decimal("0") else RatingLevel.UNAVAILABLE
            )
            contribution = (
                definition.weight_percent
                if value == Decimal("1")
                else (Decimal("0") if value == Decimal("0") else None)
            )
            return RatingIndicatorAssessment(
                code=definition.code,
                label=definition.label,
                dimension=definition.dimension,
                direction=definition.direction,
                weight_percent=definition.weight_percent,
                value=value,
                percentile_15=None,
                midpoint=None,
                percentile_85=None,
                level=level,
                contribution=contribution,
                peer_count=0,
                source_account=source_account,
            )

        peer_values = tuple(
            line.amount
            for entity_lines in by_entity.values()
            if (line := cls._find_indicator(tuple(entity_lines), definition)) is not None
        )
        if value is None or len(peer_values) < cls.MINIMUM_PEERS:
            return RatingIndicatorAssessment(
                code=definition.code,
                label=definition.label,
                dimension=definition.dimension,
                direction=definition.direction,
                weight_percent=definition.weight_percent,
                value=value,
                percentile_15=None,
                midpoint=None,
                percentile_85=None,
                level=RatingLevel.UNAVAILABLE,
                contribution=None,
                peer_count=len(peer_values),
                source_account=source_account,
            )
        percentile_15 = cls._percentile(peer_values, Decimal("0.15"))
        percentile_85 = cls._percentile(peer_values, Decimal("0.85"))
        midpoint = (percentile_15 + percentile_85) / Decimal("2")
        level = cls._level(value, percentile_15, midpoint, percentile_85, definition.direction)
        factor = {
            RatingLevel.OUTSTANDING: Decimal("1"),
            RatingLevel.SATISFACTORY: Decimal("0.75"),
            RatingLevel.IMPROVABLE: Decimal("0.50"),
            RatingLevel.CRITICAL: Decimal("0.25"),
        }[level]
        return RatingIndicatorAssessment(
            code=definition.code,
            label=definition.label,
            dimension=definition.dimension,
            direction=definition.direction,
            weight_percent=definition.weight_percent,
            value=value,
            percentile_15=percentile_15,
            midpoint=midpoint,
            percentile_85=percentile_85,
            level=level,
            contribution=definition.weight_percent * factor,
            peer_count=len(peer_values),
            source_account=source_account,
        )

    @classmethod
    def _find_indicator(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        definition: RatingIndicatorDefinition,
    ) -> FinancialStatementLine | None:
        aliases = tuple(cls._normalize(value) for value in definition.aliases)
        candidates: list[tuple[int, int, str, FinancialStatementLine]] = []
        for line in lines:
            name = cls._normalize(line.account_name)
            for alias in aliases:
                if name == alias:
                    candidates.append((0, len(name), line.account_code, line))
                elif len(alias) > 5 and name.startswith(alias):
                    candidates.append((1, len(name), line.account_code, line))
        return min(candidates, key=lambda item: item[:3])[3] if candidates else None

    @classmethod
    def _dimensions(
        cls, assessments: tuple[RatingIndicatorAssessment, ...]
    ) -> tuple[RatingDimensionAssessment, ...]:
        result: list[RatingDimensionAssessment] = []
        for name, weight in cls.DIMENSION_WEIGHTS:
            members = tuple(item for item in assessments if item.dimension == name)
            result.append(
                RatingDimensionAssessment(
                    name=name,
                    weight_percent=weight,
                    score=sum(
                        (item.contribution or Decimal("0") for item in members),
                        start=Decimal("0"),
                    ).quantize(Decimal("0.001")),
                    available_indicators=sum(item.contribution is not None for item in members),
                    total_indicators=len(members),
                )
            )
        return tuple(result)

    @staticmethod
    def _percentile(values: tuple[Decimal, ...], percentile: Decimal) -> Decimal:
        ordered = tuple(sorted(values))
        if len(ordered) == 1:
            return ordered[0]
        rank = Decimal(len(ordered) - 1) * percentile
        lower = int(rank)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = rank - Decimal(lower)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    @staticmethod
    def _level(
        value: Decimal,
        lower: Decimal,
        midpoint: Decimal,
        upper: Decimal,
        direction: RatingDirection,
    ) -> RatingLevel:
        if direction is RatingDirection.LOWER_IS_BETTER:
            if value < lower:
                return RatingLevel.OUTSTANDING
            if value < midpoint:
                return RatingLevel.SATISFACTORY
            if value < upper:
                return RatingLevel.IMPROVABLE
            return RatingLevel.CRITICAL
        if value > upper:
            return RatingLevel.OUTSTANDING
        if value > midpoint:
            return RatingLevel.SATISFACTORY
        if value > lower:
            return RatingLevel.IMPROVABLE
        return RatingLevel.CRITICAL

    @staticmethod
    def grade(score: Decimal) -> str:
        if score > Decimal("73.319"):
            return "AA"
        if score >= Decimal("64.69"):
            return "A"
        if score >= Decimal("56.067"):
            return "BB"
        if score >= Decimal("47.442"):
            return "B"
        return "CC"

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        plain = "".join(char for char in decomposed if not unicodedata.combining(char))
        return " ".join(plain.upper().split())
