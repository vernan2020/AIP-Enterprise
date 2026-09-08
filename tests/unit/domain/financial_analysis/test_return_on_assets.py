from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.domain.financial_analysis.return_on_assets import ReturnOnAssetsService


def _line(
    entity: FinancialEntity,
    cutoff: date,
    name: str,
    amount: str,
    statement_type: FinancialStatementType,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=entity,
        statement_date=cutoff,
        statement_type=statement_type,
        account_code=name[:8],
        account_name=name,
        amount=Decimal(amount),
    )


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def test_roa_uses_annualized_final_income_over_average_assets_last_12_months() -> None:
    entity = FinancialEntity("7", "Coopealianza R.L.")
    cutoff = date(2026, 8, 31)
    asset_values = [
        Decimal("780"),
        Decimal("790"),
        Decimal("800"),
        Decimal("810"),
        Decimal("820"),
        Decimal("830"),
        Decimal("840"),
        Decimal("850"),
        Decimal("860"),
        Decimal("870"),
        Decimal("880"),
        Decimal("890"),
    ]
    starts = [(2025, 9), (2025, 10), (2025, 11), (2025, 12)] + [
        (2026, month) for month in range(1, 9)
    ]
    lines = [
        _line(
            entity,
            _month_end(year, month),
            "TOTAL ACTIVO",
            str(value),
            FinancialStatementType.BALANCE_SHEET,
        )
        for (year, month), value in zip(starts, asset_values, strict=True)
    ]
    lines.append(
        _line(
            entity,
            cutoff,
            "RESULTADO DEL PERIODO",
            "8",
            FinancialStatementType.INCOME_STATEMENT,
        )
    )

    result = ReturnOnAssetsService.calculate(
        tuple(lines),
        entity_id=entity.entity_id,
        cutoff_date=cutoff,
    )

    expected_average = sum(asset_values, Decimal("0")) / Decimal("12")
    expected_annualized_income = Decimal("8") * Decimal("12") / Decimal("8")
    expected_roa = expected_annualized_income / expected_average * Decimal("100")

    assert result.status == "CALCULATED"
    assert result.asset_observations == 12
    assert result.average_assets_12m == expected_average
    assert result.annualized_net_income == expected_annualized_income
    assert result.value_percent == expected_roa


def test_roa_is_unavailable_when_any_monthly_asset_balance_is_missing() -> None:
    entity = FinancialEntity("7", "Coopealianza R.L.")
    cutoff = date(2026, 8, 31)
    lines = tuple(
        _line(
            entity,
            _month_end(2026, month),
            "TOTAL ACTIVO",
            "800",
            FinancialStatementType.BALANCE_SHEET,
        )
        for month in range(1, 9)
    ) + (
        _line(
            entity,
            cutoff,
            "RESULTADO DEL PERIODO",
            "8",
            FinancialStatementType.INCOME_STATEMENT,
        ),
    )

    result = ReturnOnAssetsService.calculate(
        lines,
        entity_id=entity.entity_id,
        cutoff_date=cutoff,
    )

    assert result.status == "INSUFFICIENT_HISTORY"
    assert result.value_percent is None
    assert result.asset_observations == 8


def test_december_income_is_not_reannualized() -> None:
    entity = FinancialEntity("7", "Coopealianza R.L.")
    cutoff = date(2026, 12, 31)
    lines = tuple(
        _line(
            entity,
            _month_end(2026, month),
            "TOTAL ACTIVO",
            "1000",
            FinancialStatementType.BALANCE_SHEET,
        )
        for month in range(1, 13)
    ) + (
        _line(
            entity,
            cutoff,
            "RESULTADO FINAL",
            "10",
            FinancialStatementType.INCOME_STATEMENT,
        ),
    )

    result = ReturnOnAssetsService.calculate(
        lines,
        entity_id=entity.entity_id,
        cutoff_date=cutoff,
    )

    assert result.annualized_net_income == Decimal("10")
    assert result.value_percent == Decimal("1")
