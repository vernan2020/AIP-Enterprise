from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    EntityFinancialRating,
    FinancialStatementLine,
    FinancialStatementType,
    RatingDirection,
    SourceTrace,
)
from aip.domain.financial_analysis.ratings import (
    FinancialEntityRatingService,
    RatingIndicatorDefinition,
)
from aip.domain.financial_analysis.return_on_assets import ReturnOnAssetsService


class SUGEFOnlyFinancialEntityRatingService(FinancialEntityRatingService):
    """Calificación 08ME14-01 con prelación estricta de fuentes oficiales.

    El ROA constituye una excepción metodológica explícita: se recalcula para
    todas las entidades con la misma fórmula institucional, utilizando utilidad
    final anualizada TTM y el promedio de los últimos 12 saldos mensuales de
    activos totales. Un ROA publicado por SUGEF nunca sustituye ese cálculo.

    Para los restantes indicadores, la información publicada por SUGEF mantiene
    precedencia sobre cualquier indicador derivado. Los cálculos 08ME14-01 solo
    funcionan como mecanismo de completitud cuando el indicador no está publicado
    y existen datos oficiales SUGEF suficientes. Los dos indicadores binarios se
    resuelven desde catálogos institucionales explícitos y auditables.
    """

    _CANONICAL_ROA_ACCOUNT = "CALC:ROA_CANONICAL"
    _SUGEF_ALIASES: dict[str, tuple[str, ...]] = {
        "ROE": ("RENTABILIDAD NOMINAL SOBRE PATRIMONIO PROMEDIO",),
        "OPERATING_EFFICIENCY": (
            "GASTOS DE ADMINISTRACION / UTILIDAD OPERACIONAL BRUTA",
            "GASTOS DE ADMINISTRACION/UTILIDAD OPERACIONAL BRUTA",
            "GASTOS ADMINISTRATIVOS / UTILIDAD OPERACIONAL BRUTA",
        ),
    }

    @classmethod
    def _find_indicator(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        definition: RatingIndicatorDefinition,
    ) -> FinancialStatementLine | None:
        if definition.code == "ROA":
            return next(
                (line for line in lines if line.account_code == cls._CANONICAL_ROA_ACCOUNT),
                None,
            )
        aliases = cls._SUGEF_ALIASES.get(definition.code, ())
        if aliases:
            definition = replace(definition, aliases=(*definition.aliases, *aliases))
        return super()._find_indicator(lines, definition)

    @classmethod
    def _source_priority(cls, line: FinancialStatementLine) -> int:
        source = cls._normalize(line.trace.source_name) if line.trace is not None else ""
        if "API PUBLICA" in source or "SUGEF" in source and "CALCULO" not in source:
            return 0
        if "CALCULO 08ME14-01" in source:
            return 1
        if "REGLA INSTITUCIONAL" in source:
            return 2
        return 3

    def evaluate(
        self,
        lines: tuple[FinancialStatementLine, ...],
        *,
        selected_entity_id: str,
        cutoff_date: date,
    ) -> EntityFinancialRating:
        canonical_roa_lines = self._canonical_roa_lines(lines, cutoff_date=cutoff_date)
        result = super().evaluate(
            (*lines, *canonical_roa_lines),
            selected_entity_id=selected_entity_id,
            cutoff_date=cutoff_date,
        )
        published = 0
        calculated = 0
        institutional = 0
        unavailable = 0
        for item in result.indicators:
            source = self._normalize(item.source_account or "")
            if "CALCULO 08ME14-01" in source or "CALCULO INSTITUCIONAL ROA" in source:
                calculated += 1
            elif "REGLA INSTITUCIONAL" in source:
                institutional += 1
            elif "SUGEF" in source or "API PUBLICA" in source:
                published += 1
            elif item.value is None:
                unavailable += 1

        diagnostics = tuple(
            message
            for message in result.diagnostics
            if "referencia institucional" not in message.lower()
            and "origen de la calificación" not in message.lower()
            and "se requieren al menos" not in message.lower()
        )
        peer_diagnostics = tuple(
            f"{item.label}: {item.peer_count} entidades comparables disponibles; "
            f"mínimo metodológico {self.MINIMUM_PEERS}."
            for item in result.indicators
            if item.direction is not RatingDirection.BINARY
            and item.value is not None
            and item.contribution is None
        )
        diagnostics = (
            *diagnostics,
            *peer_diagnostics,
            "Prelación: ROA calculado uniformemente con utilidad final anualizada TTM / "
            "promedio de 12 meses de activos; para los demás indicadores, publicación SUGEF "
            "y en su ausencia cálculo 08ME14-01; los binarios usan catálogos institucionales "
            "controlados.",
            f"Trazabilidad: {published} publicados por SUGEF, {calculated} calculados "
            f"desde datos SUGEF, {institutional} binarios institucionales y "
            f"{unavailable} no disponibles.",
        )
        return replace(result, diagnostics=diagnostics)

    @classmethod
    def _canonical_roa_lines(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        *,
        cutoff_date: date,
    ) -> tuple[FinancialStatementLine, ...]:
        entities = {
            line.entity.entity_id: line.entity
            for line in lines
            if line.statement_date == cutoff_date
        }
        output: list[FinancialStatementLine] = []
        for entity in entities.values():
            roa = ReturnOnAssetsService.calculate(
                lines,
                entity_id=entity.entity_id,
                cutoff_date=cutoff_date,
            )
            if roa.value_percent is None:
                continue
            source_line = next(
                (
                    line
                    for line in lines
                    if line.entity.entity_id == entity.entity_id
                    and line.statement_date == cutoff_date
                    and line.statement_type is FinancialStatementType.INCOME_STATEMENT
                ),
                None,
            )
            source_url = (
                source_line.trace.source_url
                if source_line is not None and source_line.trace is not None
                else ""
            )
            output.append(
                FinancialStatementLine(
                    entity=entity,
                    statement_date=cutoff_date,
                    statement_type=FinancialStatementType.INDICATORS,
                    account_code=cls._CANONICAL_ROA_ACCOUNT,
                    account_name="ROA",
                    amount=roa.value_percent / Decimal("100"),
                    currency="RATIO",
                    trace=SourceTrace(
                        source_name="Cálculo institucional ROA sobre estados financieros SUGEF",
                        source_url=source_url,
                        file_path=ReturnOnAssetsService.SOURCE_ACCOUNT,
                        sheet_name="ROA_CANONICAL",
                        row_number=0,
                    ),
                )
            )
        return tuple(output)
