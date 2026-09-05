from __future__ import annotations

from dataclasses import replace

from aip.domain.financial_analysis.models import (
    EntityFinancialRating,
    FinancialStatementLine,
    RatingDirection,
)
from aip.domain.financial_analysis.ratings import (
    FinancialEntityRatingService,
    RatingIndicatorDefinition,
)


class SUGEFOnlyFinancialEntityRatingService(FinancialEntityRatingService):
    """Calificación 08ME14-01 con prelación estricta de fuentes oficiales.

    La información publicada por SUGEF tiene precedencia sobre cualquier
    indicador derivado. Los cálculos 08ME14-01 solo funcionan como mecanismo de
    completitud cuando el indicador no está publicado y existen datos oficiales
    SUGEF suficientes. Los dos indicadores binarios se resuelven desde catálogos
    institucionales explícitos y auditables; no constituyen una fuente financiera
    alternativa ni una estimación.
    """

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

    def evaluate(self, *args: object, **kwargs: object) -> EntityFinancialRating:
        result = super().evaluate(*args, **kwargs)  # type: ignore[arg-type]
        published = 0
        calculated = 0
        institutional = 0
        unavailable = 0
        for item in result.indicators:
            source = self._normalize(item.source_account or "")
            if "CALCULO 08ME14-01" in source:
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
            "Prelación: indicador publicado por SUGEF; en su ausencia, cálculo 08ME14-01 "
            "desde datos SUGEF; los binarios usan catálogos institucionales controlados.",
            f"Trazabilidad: {published} publicados por SUGEF, {calculated} calculados "
            f"desde datos SUGEF, {institutional} binarios institucionales y "
            f"{unavailable} no disponibles.",
        )
        return replace(result, diagnostics=diagnostics)
