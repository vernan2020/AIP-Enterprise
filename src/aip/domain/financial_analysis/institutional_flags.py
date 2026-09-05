from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)


class InstitutionalEntityFlagService:
    """Genera indicadores binarios 08ME14-01 desde catálogos controlados.

    Las listas se mantienen explícitas y auditables. Una entidad no incluida en
    el catálogo aplicable recibe 0; una entidad incluida recibe 1. La comparación
    se realiza sobre nombres normalizados, sin inferencias por sector o propiedad.
    """

    _STATE_GUARANTEE = {
        "BANCO NACIONAL",
        "BANCO NACIONAL DE COSTA RICA",
        "BANCO DE COSTA RICA",
        "BANCO POPULAR",
        "BANCO POPULAR Y DE DESARROLLO COMUNAL",
        "MUTUAL ALAJUELA",
        "MUTUAL ALAJUELA DE AHORRO Y PRESTAMO",
        "MUTUAL CARTAGO",
        "MUTUAL CARTAGO DE AHORRO Y PRESTAMO",
    }
    _PROPORTIONAL_SUPERVISION = {
        "COOPAVEGRA",
        "COOPE EMPLEADOS AYA",
        "COOPE SAN MARCOS",
        "COOPEBANPO",
        "COOPECAR",
        "COOPEFYL",
        "COOPEGRECIA",
        "COOPEJUDICIALES",
        "COOPEMEDICOS",
        "COOPESANRAMON",
        "COOPEUNA",
        "CREDECOOP",
    }

    def augment(
        self,
        lines: tuple[FinancialStatementLine, ...],
        *,
        cutoff_date: date,
    ) -> tuple[FinancialStatementLine, ...]:
        entities = {
            line.entity.entity_id: line.entity
            for line in lines
            if line.statement_date == cutoff_date
        }
        additions: list[FinancialStatementLine] = []
        for entity in entities.values():
            additions.extend(self._entity_lines(entity, cutoff_date))
        return (*lines, *additions)

    @classmethod
    def _entity_lines(
        cls,
        entity: FinancialEntity,
        cutoff_date: date,
    ) -> tuple[FinancialStatementLine, FinancialStatementLine]:
        normalized = cls._normalize_entity_name(entity.name)
        state_guarantee = Decimal("1") if normalized in cls._STATE_GUARANTEE else Decimal("0")
        proportional = Decimal("1") if normalized in cls._PROPORTIONAL_SUPERVISION else Decimal("0")
        return (
            cls._line(
                entity,
                cutoff_date,
                code="PROPORTIONAL_SUPERVISION",
                label="Aplica Supervisión Proporcional",
                value=proportional,
                catalog="Catálogo institucional de entidades con supervisión proporcional",
            ),
            cls._line(
                entity,
                cutoff_date,
                code="STATE_GUARANTEE",
                label="Garantía del Estado",
                value=state_guarantee,
                catalog="Catálogo institucional de entidades con garantía del Estado",
            ),
        )

    @staticmethod
    def _line(
        entity: FinancialEntity,
        cutoff_date: date,
        *,
        code: str,
        label: str,
        value: Decimal,
        catalog: str,
    ) -> FinancialStatementLine:
        return FinancialStatementLine(
            entity=entity,
            statement_date=cutoff_date,
            statement_type=FinancialStatementType.INDICATORS,
            account_code=f"CALC:{code}",
            account_name=label,
            amount=value,
            currency="BINARY",
            trace=SourceTrace(
                source_name="Regla institucional 08ME14-01 · catálogo controlado",
                source_url="",
                file_path=catalog,
                sheet_name="08ME14-01 V01",
                row_number=0,
            ),
        )

    @classmethod
    def _normalize_entity_name(cls, value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        normalized = "".join(
            character for character in decomposed if not unicodedata.combining(character)
        ).upper()
        normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
        tokens = normalized.split()
        if len(tokens) >= 2 and tokens[-2:] == ["R", "L"]:
            tokens = tokens[:-2]
        elif tokens and tokens[-1] == "RL":
            tokens = tokens[:-1]
        return " ".join(tokens)
