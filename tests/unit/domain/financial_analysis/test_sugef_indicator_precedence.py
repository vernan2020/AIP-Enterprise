from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.indicator_calculator import OfficialRatingIndicatorCalculator
from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)

_ENTITY = FinancialEntity("3004045138", "COOPEALIANZA R.L.", "Cooperativas")
_API_TRACE = SourceTrace(
    source_name="SUGEF API pública",
    source_url="https://www.sugef.fi.cr/",
    file_path="",
    sheet_name="",
    row_number=0,
)


def _line(
    statement_date: date,
    statement_type: FinancialStatementType,
    code: str,
    name: str,
    amount: str,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=_ENTITY,
        statement_date=statement_date,
        statement_type=statement_type,
        account_code=code,
        account_name=name,
        amount=Decimal(amount),
        trace=_API_TRACE,
    )


def test_published_sugef_indicator_is_not_replaced_by_calculated_value() -> None:
    cutoff = date(2026, 7, 31)
    published = _line(
        cutoff,
        FinancialStatementType.INDICATORS,
        "ROA",
        "ROA",
        "0.0125",
    )

    augmented = OfficialRatingIndicatorCalculator().augment((published,), cutoff_date=cutoff)

    roa_lines = tuple(line for line in augmented if line.account_name == "ROA")
    assert roa_lines == (published,)
    assert all(not line.account_code.startswith("CALC:ROA") for line in augmented)


def test_missing_published_indicator_is_calculated_only_from_sugef_statements() -> None:
    cutoff = date(2026, 7, 31)
    balance_months = tuple(
        _line(
            date(year, month, day),
            FinancialStatementType.BALANCE_SHEET,
            "10000",
            "ACTIVO TOTAL",
            "1000",
        )
        for year, month, day in (
            (2025, 8, 31),
            (2025, 9, 30),
            (2025, 10, 31),
            (2025, 11, 30),
            (2025, 12, 31),
            (2026, 1, 31),
            (2026, 2, 28),
            (2026, 3, 31),
            (2026, 4, 30),
            (2026, 5, 31),
            (2026, 6, 30),
            (2026, 7, 31),
        )
    )
    results = (
        _line(
            date(2025, 7, 31),
            FinancialStatementType.INCOME_STATEMENT,
            "30000",
            "RESULTADO FINAL",
            "7",
        ),
        _line(
            date(2025, 12, 31),
            FinancialStatementType.INCOME_STATEMENT,
            "30000",
            "RESULTADO FINAL",
            "12",
        ),
        _line(
            cutoff,
            FinancialStatementType.INCOME_STATEMENT,
            "30000",
            "RESULTADO FINAL",
            "8",
        ),
    )

    augmented = OfficialRatingIndicatorCalculator().augment(
        (*balance_months, *results),
        cutoff_date=cutoff,
    )

    calculated = next(line for line in augmented if line.account_code == "CALC:ROA")
    assert calculated.amount == Decimal("0.013")
    assert calculated.trace is not None
    assert calculated.trace.source_name == "Cálculo 08ME14-01 sobre estados financieros SUGEF"


def test_missing_inputs_leave_indicator_unavailable_instead_of_using_fallback() -> None:
    cutoff = date(2026, 7, 31)
    only_current_result = _line(
        cutoff,
        FinancialStatementType.INCOME_STATEMENT,
        "30000",
        "RESULTADO FINAL",
        "8",
    )

    augmented = OfficialRatingIndicatorCalculator().augment(
        (only_current_result,),
        cutoff_date=cutoff,
    )

    assert all(line.account_code != "CALC:ROA" for line in augmented)
