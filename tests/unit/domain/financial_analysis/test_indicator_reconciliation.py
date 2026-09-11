from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.indicator_calculator import OfficialRatingIndicatorCalculator
from aip.domain.financial_analysis.indicator_reconciliation import (
    FinancialIndicatorReconciliationService,
)
from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialIndicatorReconciliationStatus,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)

_ENTITY = FinancialEntity("3004045138", "COOPEALIANZA R.L.", "Cooperativas")
_SUGEF = SourceTrace("SUGEF API pública", "https://www.sugef.fi.cr/", "api", "rows", 1)
_CALC = SourceTrace(
    "Cálculo 08ME14-01 sobre estados financieros SUGEF",
    "https://www.sugef.fi.cr/",
    "formula",
    "08ME14-01 V01",
    0,
)


def _indicator(code: str, name: str, amount: str, *, calculated: bool) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=_ENTITY,
        statement_date=date(2026, 7, 31),
        statement_type=FinancialStatementType.INDICATORS,
        account_code=f"CALC:{code}" if calculated else code,
        account_name=name,
        amount=Decimal(amount),
        currency="RATIO",
        trace=_CALC if calculated else _SUGEF,
    )


def test_reconciliation_distinguishes_match_tolerance_mismatch_and_source_gaps() -> None:
    lines = (
        _indicator("ROA", "ROA", "0.0100", calculated=False),
        _indicator("ROA", "ROA", "0.0100", calculated=True),
        _indicator("ROE", "ROE", "0.1000", calculated=False),
        _indicator("ROE", "ROE", "0.10005", calculated=True),
        _indicator(
            "CURRENT_PORTFOLIO",
            "Cartera de crédito al día",
            "0.9500",
            calculated=False,
        ),
        _indicator(
            "CURRENT_PORTFOLIO",
            "Cartera de crédito al día",
            "0.9400",
            calculated=True,
        ),
        _indicator(
            "CAPITAL_ADEQUACY",
            "Suficiencia Patrimonial",
            "0.2000",
            calculated=False,
        ),
        _indicator(
            "DELINQUENCY_90",
            "Morosidad >90 días y cobro judicial / Cartera directa",
            "0.0250",
            calculated=True,
        ),
    )

    result = FinancialIndicatorReconciliationService().reconcile(
        lines,
        entity_id=_ENTITY.entity_id,
        cutoff_date=date(2026, 7, 31),
    )
    by_code = {item.code: item for item in result}

    assert by_code["ROA"].status is FinancialIndicatorReconciliationStatus.MATCH
    assert by_code["ROE"].status is FinancialIndicatorReconciliationStatus.TOLERANCE
    assert by_code["CURRENT_PORTFOLIO"].status is FinancialIndicatorReconciliationStatus.MISMATCH
    assert (
        by_code["CAPITAL_ADEQUACY"].status is FinancialIndicatorReconciliationStatus.PUBLISHED_ONLY
    )
    assert (
        by_code["DELINQUENCY_90"].status is FinancialIndicatorReconciliationStatus.CALCULATED_ONLY
    )
    assert (
        by_code["COVERAGE_ARREARS"].status is FinancialIndicatorReconciliationStatus.MISSING_INPUT
    )
    assert by_code["CURRENT_PORTFOLIO"].difference == Decimal("-0.0100")


def test_shadow_calculation_reproduces_published_roa_without_changing_default_precedence() -> None:
    cutoff = date(2026, 12, 31)
    balances = tuple(
        FinancialStatementLine(
            entity=_ENTITY,
            statement_date=date(
                2026,
                month,
                31 if month in {1, 3, 5, 7, 8, 10, 12} else 30 if month != 2 else 28,
            ),
            statement_type=FinancialStatementType.BALANCE_SHEET,
            account_code="10000",
            account_name="ACTIVO TOTAL",
            amount=Decimal("1000"),
            trace=_SUGEF,
        )
        for month in range(1, 13)
    )
    result_line = FinancialStatementLine(
        entity=_ENTITY,
        statement_date=cutoff,
        statement_type=FinancialStatementType.INCOME_STATEMENT,
        account_code="30000",
        account_name="RESULTADO FINAL",
        amount=Decimal("10"),
        trace=_SUGEF,
    )
    published = FinancialStatementLine(
        entity=_ENTITY,
        statement_date=cutoff,
        statement_type=FinancialStatementType.INDICATORS,
        account_code="ROA",
        account_name="ROA",
        amount=Decimal("0.011"),
        currency="RATIO",
        trace=_SUGEF,
    )
    lines = (*balances, result_line, published)
    calculator = OfficialRatingIndicatorCalculator()

    normal = calculator.augment(lines, cutoff_date=cutoff)
    shadow = calculator.augment(
        lines,
        cutoff_date=cutoff,
        include_shadow_calculations=True,
    )

    assert all(line.account_code != "CALC:ROA" for line in normal)
    calculated = next(line for line in shadow if line.account_code == "CALC:ROA")
    assert calculated.amount == Decimal("0.01")
