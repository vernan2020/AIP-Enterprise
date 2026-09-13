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

_ENTITY = FinancialEntity("3004045138", "COOPEALIANZA R.L.", "Cooperativas")
_CUTOFF = date(2026, 7, 31)
_CURRENT = next(
    definition
    for definition in FinancialEntityRatingService.INDICATORS
    if definition.code == "CURRENT_PORTFOLIO"
)


def _indicator(
    code: str,
    name: str,
    value: str,
    *,
    source: str = "SUGEF - API pública de Información Financiera Contable",
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=_ENTITY,
        statement_date=_CUTOFF,
        statement_type=FinancialStatementType.INDICATORS,
        account_code=code,
        account_name=name,
        amount=Decimal(value),
        currency="RATIO",
        trace=SourceTrace(source, "https://www.sugef.fi.cr/", "api", "rows", 1),
    )


def test_current_portfolio_does_not_accept_up_to_90_days_public_indicator() -> None:
    misleading = _indicator(
        "PUBLIC:UP_TO_90",
        "Cartera al día y con atraso hasta 90 días / Cartera total",
        "0.97",
    )

    selected = SUGEFOnlyFinancialEntityRatingService._find_indicator(
        (misleading,),
        _CURRENT,
    )

    assert selected is None


def test_current_portfolio_accepts_exact_08me14_01_calculation() -> None:
    misleading = _indicator(
        "PUBLIC:UP_TO_90",
        "Cartera al día y con atraso hasta 90 días / Cartera total",
        "0.97",
    )
    calculated = _indicator(
        "CALC:CURRENT_PORTFOLIO",
        "Cartera de crédito al día",
        "0.91",
        source="Cálculo 08ME14-01 sobre cartera crediticia SUGEF",
    )

    selected = SUGEFOnlyFinancialEntityRatingService._find_indicator(
        (misleading, calculated),
        _CURRENT,
    )

    assert selected is calculated
    assert selected.amount == Decimal("0.91")
