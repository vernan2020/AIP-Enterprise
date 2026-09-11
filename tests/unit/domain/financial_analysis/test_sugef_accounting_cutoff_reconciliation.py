from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialIndicatorReconciliationStatus,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)
from aip.domain.financial_analysis.services import FinancialAnalysisService

_ENTITY = FinancialEntity("3004045138", "COOPEALIANZA R.L.", "Cooperativas")
_SUGEF = SourceTrace("SUGEF API pública", "https://www.sugef.fi.cr/", "api", "rows", 1)
_CALC = SourceTrace(
    "Cálculo 08ME14-01 sobre cartera crediticia SUGEF",
    "https://www.sugef.fi.cr/",
    "formula",
    "ReporteDiasAtraso",
    1,
)


def _line(
    statement_date: date,
    statement_type: FinancialStatementType,
    code: str,
    name: str,
    amount: str,
    *,
    trace: SourceTrace = _SUGEF,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=_ENTITY,
        statement_date=statement_date,
        statement_type=statement_type,
        account_code=code,
        account_name=name,
        amount=Decimal(amount),
        currency="RATIO" if statement_type is FinancialStatementType.INDICATORS else "CRC",
        trace=trace,
    )


def test_snapshot_uses_latest_complete_accounting_cutoff_not_newer_indicator_date() -> None:
    july = date(2026, 7, 31)
    august = date(2026, 8, 31)
    lines = (
        _line(july, FinancialStatementType.BALANCE_SHEET, "10000", "ACTIVO TOTAL", "1000"),
        _line(
            july,
            FinancialStatementType.INCOME_STATEMENT,
            "30000",
            "RESULTADO FINAL",
            "10",
        ),
        _line(august, FinancialStatementType.INDICATORS, "ROA", "ROA", "0.01"),
    )

    snapshot = FinancialAnalysisService().build_snapshot(lines, cutoff_date=august)

    assert snapshot.cutoff_date == july
    assert snapshot.status == "AVAILABLE"
    assert all(line.statement_date == july for line in snapshot.statement_lines)
    assert any("último mes con Balance de Situación" in item for item in snapshot.diagnostics)


def test_snapshot_exposes_published_vs_calculated_credit_indicator_reconciliation() -> None:
    cutoff = date(2026, 7, 31)
    lines = (
        _line(cutoff, FinancialStatementType.BALANCE_SHEET, "10000", "ACTIVO TOTAL", "1000"),
        _line(
            cutoff,
            FinancialStatementType.INCOME_STATEMENT,
            "30000",
            "RESULTADO FINAL",
            "10",
        ),
        _line(
            cutoff,
            FinancialStatementType.INDICATORS,
            "17",
            "Cartera de crédito al día",
            "0.9500",
        ),
        _line(
            cutoff,
            FinancialStatementType.INDICATORS,
            "CALC:CURRENT_PORTFOLIO",
            "Cartera de crédito al día",
            "0.9400",
            trace=_CALC,
        ),
    )

    snapshot = FinancialAnalysisService().build_snapshot(lines, cutoff_date=cutoff)
    current = next(
        item for item in snapshot.indicator_reconciliations if item.code == "CURRENT_PORTFOLIO"
    )

    assert current.published_value == Decimal("0.9500")
    assert current.calculated_value == Decimal("0.9400")
    assert current.difference == Decimal("-0.0100")
    assert current.status is FinancialIndicatorReconciliationStatus.MISMATCH
