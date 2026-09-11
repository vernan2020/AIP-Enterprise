from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.indicator_calculator import (
    OfficialRatingIndicatorCalculator,
)
from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)


def _line(
    *,
    statement_date: date,
    statement_type: FinancialStatementType,
    code: str,
    amount: str,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=FinancialEntity("3004045138", "COOPEALIANZA"),
        statement_date=statement_date,
        statement_type=statement_type,
        account_code=code,
        account_name=code,
        amount=Decimal(amount),
        trace=SourceTrace("SUGEF API", "https://sugef.example", "api", "rows", 1),
    )


def test_calculates_word_methodology_indicators_from_twelve_months() -> None:
    cutoff = date(2026, 7, 31)
    months = (
        date(2025, 8, 31),
        date(2025, 9, 30),
        date(2025, 10, 31),
        date(2025, 11, 30),
        date(2025, 12, 31),
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
        date(2026, 5, 31),
        date(2026, 6, 30),
        cutoff,
    )
    lines = tuple(
        line
        for month in months
        for line in (
            _line(
                statement_date=month,
                statement_type=FinancialStatementType.BALANCE_SHEET,
                code="10000",
                amount="1200",
            ),
            _line(
                statement_date=month,
                statement_type=FinancialStatementType.BALANCE_SHEET,
                code="25000",
                amount="240",
            ),
        )
    ) + tuple(
        _line(
            statement_date=statement_date,
            statement_type=FinancialStatementType.INCOME_STATEMENT,
            code=code,
            amount=amount,
        )
        for code, values in {
            "31300": ("50", "100", "70"),
            "31000": ("75", "150", "100"),
            "32000": ("30", "60", "40"),
            "30000": ("10", "20", "14"),
        }.items()
        for statement_date, amount in zip(
            (date(2025, 7, 31), date(2025, 12, 31), cutoff), values, strict=True
        )
    )

    augmented = OfficialRatingIndicatorCalculator().augment(lines, cutoff_date=cutoff)
    calculated = {
        line.account_code: line.amount
        for line in augmented
        if line.account_code.startswith("CALC:")
    }

    assert calculated == {
        "CALC:MARGIN_INTERMEDIATION": Decimal("0.1"),
        "CALC:ROA": Decimal("0.02"),
        "CALC:ROE": Decimal("0.1"),
        "CALC:OPERATING_EFFICIENCY": Decimal("0.4"),
        "CALC:ADMIN_EXPENSE_ASSETS": Decimal("0.05833333333333333333333333333"),
    }
    assert all(
        line.trace is not None and "08ME14-01" in line.trace.source_name
        for line in augmented
        if line.account_code.startswith("CALC:")
    )


def test_does_not_approximate_twelve_month_average_when_history_is_incomplete() -> None:
    cutoff = date(2026, 7, 31)
    lines = (
        _line(
            statement_date=cutoff,
            statement_type=FinancialStatementType.BALANCE_SHEET,
            code="10000",
            amount="1200",
        ),
        _line(
            statement_date=cutoff,
            statement_type=FinancialStatementType.INCOME_STATEMENT,
            code="30000",
            amount="14",
        ),
    )

    augmented = OfficialRatingIndicatorCalculator().augment(lines, cutoff_date=cutoff)

    assert not any(line.account_code == "CALC:ROA" for line in augmented)
