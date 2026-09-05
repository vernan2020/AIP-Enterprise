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

_CUTOFF = date(2026, 7, 31)


def test_capital_adequacy_rating_source_preserves_official_quarterly_cutoff() -> None:
    entities = (
        FinancialEntity("1", "Entidad 1"),
        FinancialEntity("2", "Entidad 2"),
        FinancialEntity("3", "Entidad 3"),
    )
    lines = tuple(
        FinancialStatementLine(
            entity=entity,
            statement_date=_CUTOFF,
            statement_type=FinancialStatementType.INDICATORS,
            account_code="SUGEF:CAPITAL_ADEQUACY",
            account_name="Suficiencia Patrimonial",
            amount=Decimal(value),
            currency="RATIO",
            trace=SourceTrace(
                source_name="SUGEF · Suficiencia Patrimonial trimestral",
                source_url="https://www.sugef.fi.cr/reportes/Suficiencia%20Patrimonial.aspx",
                file_path="corte oficial 30/06/2026",
                sheet_name="Suficiencia",
                row_number=index,
            ),
        )
        for index, (entity, value) in enumerate(
            zip(entities, ("0.20", "0.18", "0.16"), strict=True),
            start=1,
        )
    )

    rating = FinancialEntityRatingService().evaluate(
        lines,
        selected_entity_id="1",
        cutoff_date=_CUTOFF,
    )
    capital_adequacy = next(
        item for item in rating.indicators if item.code == "CAPITAL_ADEQUACY"
    )

    assert capital_adequacy.value == Decimal("0.20")
    assert capital_adequacy.source_account is not None
    assert "SUGEF · Suficiencia Patrimonial trimestral" in capital_adequacy.source_account
    assert "corte oficial 30/06/2026" in capital_adequacy.source_account
