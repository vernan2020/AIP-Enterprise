from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import FinancialAnalysisSnapshot
from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
    FinancialAnalysisPresenter,
)


def test_excel_relative_letter_does_not_mask_fixed_document_letter() -> None:
    snapshot = FinancialAnalysisSnapshot(
        status="PARTIAL",
        cutoff_date=date(2026, 8, 31),
        selected_entity=None,
        reference_matrix_score=Decimal("64.7975"),
        reference_matrix_grade="BB",
        reference_matrix_maximum=Decimal("86.6750"),
        reference_matrix_coverage="38/38; Estado: APTA",
    )
    vm = FinancialAnalysisPresenter._from_snapshot(snapshot)
    assert "Perfil Excel agosto 2026" in vm.score_matrix_summary
    assert "(BB)" in vm.score_matrix_summary
    assert "escala fija del documento: A" in vm.score_matrix_summary
    assert "no nueva nota normativa" in vm.score_matrix_summary
