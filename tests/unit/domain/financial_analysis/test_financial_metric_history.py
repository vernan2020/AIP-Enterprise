from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)

ENTITY = FinancialEntity("3004045138", "COOPEALIANZA R.L.")


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def _line(
    statement_date: date,
    statement_type: FinancialStatementType,
    account_code: str,
    account_name: str,
    amount: Decimal,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=ENTITY,
        statement_date=statement_date,
        statement_type=statement_type,
        account_code=account_code,
        account_name=account_name,
        amount=amount,
    )


def _history_lines(
    *,
    missing_month: date | None = None,
) -> tuple[FinancialStatementLine, ...]:
    lines: list[FinancialStatementLine] = []
    start_index = 2024 * 12 + 7  # August 2024, zero-based month index.
    for index in range(24):
        year, zero_based_month = divmod(start_index + index, 12)
        statement_date = _month_end(year, zero_based_month + 1)
        if statement_date == missing_month:
            continue
        assets = Decimal("800000000000") + Decimal(index) * Decimal("1000000000")
        lines.extend(
            (
                _line(
                    statement_date,
                    FinancialStatementType.BALANCE_SHEET,
                    "10000",
                    "ACTIVO TOTAL",
                    assets,
                ),
                _line(
                    statement_date,
                    FinancialStatementType.BALANCE_SHEET,
                    "12000",
                    "CARTERA DE CREDITO",
                    Decimal("410000000000") + Decimal(index) * Decimal("500000000"),
                ),
                _line(
                    statement_date,
                    FinancialStatementType.BALANCE_SHEET,
                    "20000",
                    "PASIVO TOTAL",
                    Decimal("610000000000") + Decimal(index) * Decimal("700000000"),
                ),
                _line(
                    statement_date,
                    FinancialStatementType.BALANCE_SHEET,
                    "25000",
                    "PATRIMONIO TOTAL",
                    Decimal("190000000000") + Decimal(index) * Decimal("300000000"),
                ),
                _line(
                    statement_date,
                    FinancialStatementType.INCOME_STATEMENT,
                    "30000",
                    "RESULTADO FINAL",
                    Decimal("7000000000") + Decimal(index) * Decimal("100000000"),
                ),
                _line(
                    statement_date,
                    FinancialStatementType.INDICATORS,
                    "81000",
                    "ROA",
                    Decimal("0.010") + Decimal(index) * Decimal("0.0001"),
                ),
                _line(
                    statement_date,
                    FinancialStatementType.INDICATORS,
                    "82000",
                    "ROE",
                    Decimal("0.050") + Decimal(index) * Decimal("0.0002"),
                ),
            )
        )
    return tuple(lines)


def _build_history(*, missing_month: date | None = None):
    from aip.domain.financial_analysis.financial_metric_history import (
        FinancialMetricHistoryService,
    )

    return FinancialMetricHistoryService().build(
        _history_lines(missing_month=missing_month),
        entity_id=ENTITY.entity_id,
        cutoff_date=date(2026, 7, 31),
    )


def test_history_builds_seven_kpis_for_twelve_monthly_cutoffs() -> None:
    series = _build_history()

    assert tuple(item.code for item in series) == (
        "ASSETS",
        "LOANS",
        "LIABILITIES",
        "EQUITY",
        "NET_INCOME",
        "ROA",
        "ROE",
    )
    assert all(len(item.points) == 12 for item in series)
    assets = next(item for item in series if item.code == "ASSETS")
    assert assets.points[0].statement_date == date(2025, 8, 31)
    assert assets.points[-1].statement_date == date(2026, 7, 31)
    assert assets.points[-1].value == Decimal("823000000000")


def test_history_preserves_missing_month_as_none_instead_of_zero() -> None:
    series = _build_history(missing_month=date(2025, 12, 31))

    assets = next(item for item in series if item.code == "ASSETS")
    december = next(point for point in assets.points if point.statement_date == date(2025, 12, 31))
    assert december.value is None
    assert all(point.value != Decimal("0") for point in assets.points if point.value is not None)


def test_history_calculates_roa_from_annualized_income_and_12_month_average_assets() -> None:
    series = _build_history()

    roa = next(item for item in series if item.code == "ROA")
    roe = next(item for item in series if item.code == "ROE")

    current_assets = [
        Decimal("812000000000") + Decimal(index) * Decimal("1000000000")
        for index in range(12)
    ]
    average_assets = sum(current_assets, Decimal("0")) / Decimal("12")
    current_income = Decimal("9300000000")
    prior_december_income = Decimal("8600000000")
    prior_same_month_income = Decimal("8100000000")
    annualized_income = current_income + prior_december_income - prior_same_month_income
    expected_roa = annualized_income / average_assets * Decimal("100")

    assert roa.points[-1].value == expected_roa
    assert roa.source_account is not None
    assert "promedio últimos 12 meses" in roa.source_account
    assert roa.points[-1].value != Decimal("1.2300")
    assert roe.points[-1].value == Decimal("5.4600")
