from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialAnalysisSnapshot,
    FinancialEntity,
    FinancialIndicatorReconciliation,
    FinancialIndicatorReconciliationStatus,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
    FinancialAnalysisPresenter,
)


def test_presenter_formats_reconciliation_and_binary_statement_values() -> None:
    entity = FinancialEntity("3004045138", "COOPEALIANZA R.L.", "Cooperativas")
    cutoff = date(2026, 7, 31)
    snapshot = FinancialAnalysisSnapshot(
        status="AVAILABLE",
        cutoff_date=cutoff,
        selected_entity=entity,
        entities=(entity,),
        available_dates=(cutoff,),
        statement_lines=(
            FinancialStatementLine(
                entity=entity,
                statement_date=cutoff,
                statement_type=FinancialStatementType.INDICATORS,
                account_code="CALC:STATE_GUARANTEE",
                account_name="Garantía del Estado",
                amount=Decimal("0"),
                currency="BINARY",
            ),
        ),
        indicator_reconciliations=(
            FinancialIndicatorReconciliation(
                code="LIQUIDITY_COVERAGE",
                label="Liquidez",
                published_value=Decimal("0.50"),
                calculated_value=Decimal("0.49"),
                difference=Decimal("-0.01"),
                tolerance=Decimal("0.0001"),
                status=FinancialIndicatorReconciliationStatus.MISMATCH,
                published_source="SUGEF · indicador publicado",
                calculated_source="Cálculo 08ME14-01",
            ),
            FinancialIndicatorReconciliation(
                code="STATE_GUARANTEE",
                label="Garantía del Estado",
                published_value=None,
                calculated_value=Decimal("0"),
                difference=None,
                tolerance=Decimal("0.0001"),
                status=FinancialIndicatorReconciliationStatus.CALCULATED_ONLY,
                calculated_source="Regla institucional",
            ),
        ),
    )

    view_model = FinancialAnalysisPresenter._from_snapshot(snapshot)

    assert view_model.statement_rows[0].amount == "No"
    liquidity = view_model.indicator_reconciliations[0]
    assert liquidity.published_value == "50.000%"
    assert liquidity.calculated_value == "49.000%"
    assert liquidity.difference == "-1.000 pp"
    assert liquidity.status == "Diferencia"
    guarantee = view_model.indicator_reconciliations[1]
    assert guarantee.calculated_value == "No (0)"
    assert guarantee.status == "Solo AIP"
