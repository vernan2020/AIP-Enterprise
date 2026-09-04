from __future__ import annotations

from dataclasses import replace

from aip.domain.financial_analysis.models import (
    EntityFinancialRating,
    FinancialStatementLine,
)
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService


class SUGEFOnlyFinancialEntityRatingService(FinancialEntityRatingService):
    """Calificación 08ME14-01 con prelación estricta de fuentes SUGEF.

    La API publicada por SUGEF tiene precedencia sobre cualquier indicador
    derivado. Los cálculos 08ME14-01 solo funcionan como mecanismo de completitud
    cuando el indicador no está publicado y existen estados financieros SUGEF
    suficientes. No se admite una tercera fuente de respaldo.
    """

    @classmethod
    def _source_priority(cls, line: FinancialStatementLine) -> int:
        source = cls._normalize(line.trace.source_name) if line.trace is not None else ""
        if "API PUBLICA" in source or "SUGEF" in source and "CALCULO" not in source:
            return 0
        if "CALCULO 08ME14-01" in source:
            return 1
        return 2

    def evaluate(self, *args: object, **kwargs: object) -> EntityFinancialRating:
        result = super().evaluate(*args, **kwargs)  # type: ignore[arg-type]
        published = 0
        calculated = 0
        unavailable = 0
        for item in result.indicators:
            source = (item.source_account or "").upper()
            if "CALCULO 08ME14-01" in source:
                calculated += 1
            elif "SUGEF" in source or "API PUBLICA" in source:
                published += 1
            elif item.value is None:
                unavailable += 1

        diagnostics = tuple(
            message
            for message in result.diagnostics
            if "referencia institucional" not in message.lower()
            and "origen de la calificación" not in message.lower()
        )
        diagnostics = (
            *diagnostics,
            "Prelación de fuentes: indicador publicado por SUGEF; en su ausencia, "
            "cálculo 08ME14-01 desde estados financieros SUGEF; sin otra fuente de respaldo.",
            f"Trazabilidad: {published} publicados por SUGEF, {calculated} calculados "
            f"desde estados financieros SUGEF y {unavailable} no disponibles.",
        )
        return replace(result, diagnostics=diagnostics)
