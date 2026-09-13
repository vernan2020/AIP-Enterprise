from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.domain.financial_analysis.services import FinancialAnalysisService
from aip.domain.financial_analysis.sugef_ratings import SUGEFOnlyFinancialEntityRatingService


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def _line(
    entity: FinancialEntity,
    statement_date: date,
    statement_type: FinancialStatementType,
    account_code: str,
    account_name: str,
    amount: str,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=entity,
        statement_date=statement_date,
        statement_type=statement_type,
        account_code=account_code,
        account_name=account_name,
        amount=Decimal(amount),
    )


def _complete_roa_history(
    entity: FinancialEntity,
    *,
    assets: str,
    prior_same_month_income: str,
    prior_december_income: str,
    current_income: str,
    published_roa: str,
) -> tuple[FinancialStatementLine, ...]:
    cutoff = date(2026, 7, 31)
    asset_months = [(2025, month) for month in range(8, 13)] + [
        (2026, month) for month in range(1, 8)
    ]
    lines = [
        _line(
            entity,
            _month_end(year, month),
            FinancialStatementType.BALANCE_SHEET,
            "10000",
            "ACTIVO TOTAL",
            assets,
        )
        for year, month in asset_months
    ]
    lines.extend(
        (
            _line(
                entity,
                date(2025, 7, 31),
                FinancialStatementType.INCOME_STATEMENT,
                "30000",
                "RESULTADO FINAL",
                prior_same_month_income,
            ),
            _line(
                entity,
                date(2025, 12, 31),
                FinancialStatementType.INCOME_STATEMENT,
                "30000",
                "RESULTADO FINAL",
                prior_december_income,
            ),
            _line(
                entity,
                cutoff,
                FinancialStatementType.INCOME_STATEMENT,
                "30000",
                "RESULTADO FINAL",
                current_income,
            ),
            _line(
                entity,
                cutoff,
                FinancialStatementType.INDICATORS,
                "SUGEF:ROA",
                "ROA",
                published_roa,
            ),
        )
    )
    return tuple(lines)


def test_peer_summaries_use_same_canonical_roa_and_never_published_fallback() -> None:
    cutoff = date(2026, 7, 31)
    first = FinancialEntity("1", "Entidad Uno", "Cooperativas")
    second = FinancialEntity("2", "Entidad Dos", "Cooperativas")
    incomplete = FinancialEntity("3", "Entidad Incompleta", "Cooperativas")

    lines = (
        *_complete_roa_history(
            first,
            assets="1000",
            prior_same_month_income="60",
            prior_december_income="120",
            current_income="80",
            published_roa="0.9999",
        ),
        *_complete_roa_history(
            second,
            assets="2000",
            prior_same_month_income="100",
            prior_december_income="200",
            current_income="120",
            published_roa="0.8888",
        ),
        _line(
            incomplete,
            cutoff,
            FinancialStatementType.BALANCE_SHEET,
            "10000",
            "ACTIVO TOTAL",
            "3000",
        ),
        _line(
            incomplete,
            cutoff,
            FinancialStatementType.INCOME_STATEMENT,
            "30000",
            "RESULTADO FINAL",
            "300",
        ),
        _line(
            incomplete,
            cutoff,
            FinancialStatementType.INDICATORS,
            "SUGEF:ROA",
            "ROA",
            "0.7777",
        ),
    )

    snapshot = FinancialAnalysisService().build_snapshot(
        tuple(lines),
        selected_entity_id=first.entity_id,
        cutoff_date=cutoff,
    )
    peers = {item.entity.entity_id: item for item in snapshot.peer_summaries}

    assert peers[first.entity_id].roa_percent == Decimal("14")
    assert peers[second.entity_id].roa_percent == Decimal("11")
    assert peers[first.entity_id].roa_percent != Decimal("99.99")
    assert peers[second.entity_id].roa_percent != Decimal("88.88")
    assert peers[incomplete.entity_id].roa_percent is None


def test_rating_uses_canonical_roa_for_selected_entity_and_peer_distribution() -> None:
    cutoff = date(2026, 7, 31)
    first = FinancialEntity("1", "Entidad Uno", "Cooperativas")
    second = FinancialEntity("2", "Entidad Dos", "Cooperativas")
    third = FinancialEntity("3", "Entidad Tres", "Cooperativas")

    lines = (
        *_complete_roa_history(
            first,
            assets="1000",
            prior_same_month_income="60",
            prior_december_income="120",
            current_income="80",
            published_roa="0.9999",
        ),
        *_complete_roa_history(
            second,
            assets="2000",
            prior_same_month_income="100",
            prior_december_income="200",
            current_income="120",
            published_roa="0.8888",
        ),
        *_complete_roa_history(
            third,
            assets="4000",
            prior_same_month_income="100",
            prior_december_income="300",
            current_income="200",
            published_roa="0.7777",
        ),
    )

    rating = SUGEFOnlyFinancialEntityRatingService().evaluate(
        tuple(lines),
        selected_entity_id=first.entity_id,
        cutoff_date=cutoff,
    )
    roa = next(item for item in rating.indicators if item.code == "ROA")

    assert roa.value == Decimal("0.14")
    assert roa.peer_count == 3
    assert roa.value != Decimal("0.9999")
    assert roa.source_account is not None
    assert "Cálculo institucional ROA" in roa.source_account
