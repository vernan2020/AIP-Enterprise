from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService
from aip.domain.financial_analysis.sugef_ratings import SUGEFOnlyFinancialEntityRatingService

CUTOFF = date(2026, 7, 31)


def _published_line(
    entity_id: str,
    name: str,
    value: str,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=FinancialEntity(entity_id, f"Entidad {entity_id}"),
        statement_date=CUTOFF,
        statement_type=FinancialStatementType.INDICATORS,
        account_code=f"SUGEF-{entity_id}",
        account_name=name,
        amount=Decimal(value),
        trace=SourceTrace(
            source_name="SUGEF - API pública de Información Financiera Contable",
            source_url="https://www.sugef.fi.cr",
            file_path="api",
            sheet_name="indicadores",
            row_number=1,
        ),
    )


def _definition(code: str):
    return next(item for item in FinancialEntityRatingService.INDICATORS if item.code == code)


def test_sugef_rating_recognizes_published_roe_name() -> None:
    line = _published_line(
        "1",
        "Rentabilidad nominal sobre Patrimonio Promedio",
        "0.05735",
    )

    selected = SUGEFOnlyFinancialEntityRatingService._find_indicator(
        (line,),
        _definition("ROE"),
    )

    assert selected is line


def test_sugef_rating_recognizes_published_operating_efficiency_name() -> None:
    line = _published_line(
        "1",
        "Gastos de Administración / Utilidad Operacional bruta",
        "0.46221",
    )

    selected = SUGEFOnlyFinancialEntityRatingService._find_indicator(
        (line,),
        _definition("OPERATING_EFFICIENCY"),
    )

    assert selected is line


def test_sugef_rating_reports_actual_comparable_population() -> None:
    lines = (
        _published_line("1", "Rentabilidad nominal sobre Patrimonio Promedio", "0.05735"),
        _published_line("2", "Rentabilidad nominal sobre Patrimonio Promedio", "0.06100"),
    )

    result = SUGEFOnlyFinancialEntityRatingService().evaluate(
        lines,
        selected_entity_id="1",
        cutoff_date=CUTOFF,
    )

    roe = next(item for item in result.indicators if item.code == "ROE")
    assert roe.value == Decimal("0.05735")
    assert roe.peer_count == 2
    assert roe.contribution is None
    assert any(
        "ROE: 2 entidades comparables disponibles" in message for message in result.diagnostics
    )
