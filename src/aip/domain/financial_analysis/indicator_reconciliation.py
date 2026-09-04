from __future__ import annotations

import unicodedata
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialIndicatorReconciliation,
    FinancialIndicatorReconciliationStatus,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService


class FinancialIndicatorReconciliationService:
    """Compara indicadores publicados por SUGEF contra cálculos 08ME14-01.

    La reconciliación no altera la precedencia usada para calificar. El valor
    oficial publicado por SUGEF conserva prioridad; este servicio únicamente
    expone, en paralelo, el valor reproducido por AIP y su diferencia.
    """

    DEFAULT_TOLERANCE = Decimal("0.0001")  # 1 punto base expresado como razón.

    # Alias públicos adicionales observados en el reporte de indicadores SUGEF.
    _PUBLIC_ALIASES: dict[str, tuple[str, ...]] = {
        "ROE": ("RENTABILIDAD NOMINAL SOBRE PATRIMONIO PROMEDIO",),
        "OPERATING_EFFICIENCY": (
            "GASTOS DE ADMINISTRACION / UTILIDAD OPERACIONAL BRUTA",
            "GASTOS DE ADMINISTRACION/UTILIDAD OPERACIONAL BRUTA",
            "GASTOS ADMINISTRATIVOS / UTILIDAD OPERACIONAL BRUTA",
        ),
    }

    def __init__(self, *, tolerance: Decimal | None = None) -> None:
        self._tolerance = tolerance if tolerance is not None else self.DEFAULT_TOLERANCE

    def reconcile(
        self,
        lines: tuple[FinancialStatementLine, ...],
        *,
        entity_id: str,
        cutoff_date,
    ) -> tuple[FinancialIndicatorReconciliation, ...]:
        current = tuple(
            line
            for line in lines
            if line.entity.entity_id == entity_id
            and line.statement_date == cutoff_date
            and line.statement_type is FinancialStatementType.INDICATORS
        )
        output: list[FinancialIndicatorReconciliation] = []
        for definition in FinancialEntityRatingService.INDICATORS:
            aliases = (*definition.aliases, *self._PUBLIC_ALIASES.get(definition.code, ()))
            published = self._published(current, aliases)
            calculated = self._calculated(current, definition.code)
            output.append(
                self._build(
                    code=definition.code,
                    label=definition.label,
                    published=published,
                    calculated=calculated,
                )
            )
        return tuple(output)

    def _build(
        self,
        *,
        code: str,
        label: str,
        published: FinancialStatementLine | None,
        calculated: FinancialStatementLine | None,
    ) -> FinancialIndicatorReconciliation:
        published_value = published.amount if published is not None else None
        calculated_value = calculated.amount if calculated is not None else None
        difference = None
        if published_value is not None and calculated_value is not None:
            difference = calculated_value - published_value
            absolute = abs(difference)
            if absolute == Decimal("0"):
                status = FinancialIndicatorReconciliationStatus.MATCH
            elif absolute <= self._tolerance:
                status = FinancialIndicatorReconciliationStatus.TOLERANCE
            else:
                status = FinancialIndicatorReconciliationStatus.MISMATCH
        elif published_value is not None:
            status = FinancialIndicatorReconciliationStatus.PUBLISHED_ONLY
        elif calculated_value is not None:
            status = FinancialIndicatorReconciliationStatus.CALCULATED_ONLY
        else:
            status = FinancialIndicatorReconciliationStatus.MISSING_INPUT

        return FinancialIndicatorReconciliation(
            code=code,
            label=label,
            published_value=published_value,
            calculated_value=calculated_value,
            difference=difference,
            tolerance=self._tolerance,
            status=status,
            published_source=self._source(published),
            calculated_source=self._source(calculated),
        )

    @classmethod
    def _published(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        aliases: tuple[str, ...],
    ) -> FinancialStatementLine | None:
        normalized_aliases = tuple(cls._normalize(alias) for alias in aliases)
        candidates = []
        for line in lines:
            if line.account_code.startswith("CALC:"):
                continue
            name = cls._normalize(line.account_name)
            if any(name == alias or (len(alias) > 5 and name.startswith(alias)) for alias in normalized_aliases):
                candidates.append(line)
        if not candidates:
            return None
        return min(candidates, key=lambda item: item.account_code)

    @staticmethod
    def _calculated(
        lines: tuple[FinancialStatementLine, ...],
        code: str,
    ) -> FinancialStatementLine | None:
        expected = f"CALC:{code}"
        return next((line for line in lines if line.account_code == expected), None)

    @staticmethod
    def _source(line: FinancialStatementLine | None) -> str | None:
        if line is None:
            return None
        if line.trace is None:
            return line.account_code or line.account_name
        return f"{line.trace.source_name} · {line.account_code or line.account_name}"

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        return " ".join(
            "".join(character for character in decomposed if not unicodedata.combining(character))
            .upper()
            .split()
        )
