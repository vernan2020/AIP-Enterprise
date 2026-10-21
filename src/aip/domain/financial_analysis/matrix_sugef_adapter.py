"""Adapter from real SUGEF financial statements to the validated Excel engine.

The institution universe is explicit and versioned from the August 2026 matrix.
AIP never imports that confidential workbook or substitutes missing indicators.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.matrix_reference_rating import (
    MatrixCohortResult,
    MatrixEntityInput,
    MatrixReferenceRatingService,
)
from aip.domain.financial_analysis.models import FinancialStatementLine
from aip.domain.financial_analysis.sugef_ratings import (
    SUGEFOnlyFinancialEntityRatingService,
)

# Public institutional names from the August 2026 approved comparison universe.
REFERENCE_AUGUST_2026_CODES: tuple[str, ...] = (
    "BANCO BAC SANJOSE",
    "BANCO BCT",
    "BANCO CMB",
    "BANCO DE COSTA RICA",
    "BANCO GENERAL",
    "BANCO NACIONAL",
    "BANCO POPULAR",
    "BANHVI",
    "CAJA DE ANDE",
    "BANCO CATHAY",
    "COOCIQUE",
    "COOPAVEGRA",
    "COOPEAYA",
    "COOPESANMARCOS",
    "COOPEALIANZA",
    "COOPEANDE",
    "COOPEBANPO",
    "COOPECAJA",
    "COOPECAR",
    "COOPEFYL",
    "COOPEGRECIA",
    "COOPEJUDICIAL",
    "COOPEMEDICOS",
    "COOPEMEP",
    "COOPENAE",
    "COOPESANRAMON",
    "COOPEUNA",
    "CREDECOOP",
    "BANCO DAVIVIENDA",
    "FINANCIERA CAFSA",
    "FINANCIERA COMECA",
    "FINANCIERA MONGE",
    "BANCO IMPROSA",
    "BANCO LAFISE",
    "GRUPO MUTUAL",
    "MUCAP",
    "BANCO PROMERICA",
    "DAVIBANK",
)


class MatrixSUGEFAdapter:
    """Extract only published or traceable SUGEF-derived ratios for one cohort."""

    @staticmethod
    def _code(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        stripped = "".join(
            character for character in normalized if not unicodedata.combining(character)
        )
        return re.sub(r"[^A-Z0-9]+", " ", stripped.upper()).strip()

    @classmethod
    def select_reference_entities(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        cutoff_date: date,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        entities = {
            line.entity.entity_id: line.entity
            for line in lines
            if line.statement_date == cutoff_date
        }
        matched: dict[str, str] = {}
        for entity in entities.values():
            stem = re.split(r"\s+[-–—]\s+", entity.name, maxsplit=1)[0]
            normalized = cls._code(stem)
            for expected in REFERENCE_AUGUST_2026_CODES:
                if normalized == expected or normalized.startswith(expected + " "):
                    if expected in matched:
                        raise ValueError(f"Duplicidad de catálogo: {expected}")
                    matched[expected] = entity.entity_id
                    break
        missing = tuple(code for code in REFERENCE_AUGUST_2026_CODES if code not in matched)
        return tuple(matched.values()), missing

    @classmethod
    def extract(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        *,
        cutoff_date: date,
        cohort_ids: tuple[str, ...],
    ) -> tuple[MatrixEntityInput, ...]:
        """Enforce the requested cohort; missing rows stay missing."""
        ids = set(cohort_ids)
        if not ids or len(ids) != len(cohort_ids):
            raise ValueError("La cohorte debe contener IDs distintos.")
        by_entity: dict[str, list[FinancialStatementLine]] = defaultdict(list)
        for line in lines:
            if line.statement_date == cutoff_date and line.entity.entity_id in ids:
                by_entity[line.entity.entity_id].append(line)
        if ids - set(by_entity):
            raise ValueError("La cohorte solicitada contiene entidades sin datos del corte.")

        reference = SUGEFOnlyFinancialEntityRatingService()
        canonical = reference._canonical_roa_lines(lines, cutoff_date=cutoff_date)
        for line in canonical:
            if line.entity.entity_id in ids:
                by_entity[line.entity.entity_id].append(line)
        output: list[MatrixEntityInput] = []
        for entity_id in cohort_ids:
            source_lines = tuple(by_entity[entity_id])
            ratios: dict[str, Decimal | None] = {}
            for definition in reference.INDICATORS:
                observed = reference._find_indicator(source_lines, definition)
                ratios[definition.code] = observed.amount if observed is not None else None
            proportional = ratios["PROPORTIONAL_SUPERVISION"]
            guarantee = ratios["STATE_GUARANTEE"]
            output.append(
                MatrixEntityInput(
                    entity_id=entity_id,
                    name=source_lines[0].entity.name,
                    indicators=ratios,
                    regulation_full=(
                        (proportional == Decimal("0"))
                        if proportional in (Decimal("0"), Decimal("1"))
                        else None
                    ),
                    state_guarantee=(
                        (guarantee == Decimal("1"))
                        if guarantee in (Decimal("0"), Decimal("1"))
                        else None
                    ),
                )
            )
        return tuple(output)

    @classmethod
    def validate_reference_cohort(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        cutoff_date: date,
    ) -> tuple[MatrixCohortResult, tuple[str, ...]]:
        ids, missing = cls.select_reference_entities(lines, cutoff_date)
        if len(ids) < 3:
            raise ValueError("Cohorte SUGEF insuficiente para calcular percentiles.")
        inputs = cls.extract(lines, cutoff_date=cutoff_date, cohort_ids=ids)
        result = MatrixReferenceRatingService.evaluate(inputs)
        return result, missing
