from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    RatingDirection,
    SourceTrace,
)
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService
from aip.domain.financial_analysis.sugef_ratings import SUGEFOnlyFinancialEntityRatingService

_CUTOFF = date(2026, 7, 31)
_ENTITIES = (
    FinancialEntity("3004045138", "COOPEALIANZA R.L.", "Cooperativas"),
    FinancialEntity("PEER-1", "COOPERATIVA PAR 1", "Cooperativas"),
    FinancialEntity("PEER-2", "COOPERATIVA PAR 2", "Cooperativas"),
)
_TRACE = SourceTrace(
    source_name="SUGEF - API pública de Información Financiera Contable",
    source_url="https://www.sugef.fi.cr/",
    file_path="api",
    sheet_name="indicadores",
    row_number=1,
)


def _value(direction: RatingDirection, entity_index: int) -> Decimal:
    if direction is RatingDirection.BINARY:
        return Decimal("0")
    if direction is RatingDirection.HIGHER_IS_BETTER:
        return (Decimal("3") - Decimal(entity_index)) / Decimal("10")
    return (Decimal("1") + Decimal(entity_index)) / Decimal("10")


def _complete_lines() -> tuple[FinancialStatementLine, ...]:
    lines: list[FinancialStatementLine] = []
    for definition in FinancialEntityRatingService.INDICATORS:
        for entity_index, entity in enumerate(_ENTITIES):
            lines.append(
                FinancialStatementLine(
                    entity=entity,
                    statement_date=_CUTOFF,
                    statement_type=FinancialStatementType.INDICATORS,
                    account_code=definition.code,
                    account_name=definition.label,
                    amount=_value(definition.direction, entity_index),
                    currency="RATIO",
                    trace=_TRACE,
                )
            )
    return tuple(lines)


def test_rating_is_emitted_when_all_13_methodology_indicators_are_available() -> None:
    rating = SUGEFOnlyFinancialEntityRatingService().evaluate(
        _complete_lines(),
        selected_entity_id=_ENTITIES[0].entity_id,
        cutoff_date=_CUTOFF,
    )

    assert rating.status == "COMPLETE"
    assert rating.coverage_percent == Decimal("100.00")
    assert len(rating.indicators) == 13
    assert all(item.contribution is not None for item in rating.indicators)
    assert rating.score is not None
    assert rating.grade is not None
    assert not any(message.startswith("Falta el indicador:") for message in rating.diagnostics)
