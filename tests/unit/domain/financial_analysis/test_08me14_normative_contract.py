"""Contract of the currently presented 08ME14-01 V01 document.

The normative fixed rating scale and the spreadsheet's cohort-relative
rating scale are separate. This audit must not replace production methods
until a documented methodological decision has been approved.
"""

from __future__ import annotations

from decimal import Decimal

from aip.domain.financial_analysis.matrix_reference_rating import (
    MatrixReferenceRatingService,
)
from aip.domain.financial_analysis.rating_score_audit import RatingScoreAuditService
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService


def test_normative_document_uses_fixed_classification_not_excel_relative_max() -> None:
    score = Decimal("64.7975")
    assert FinancialEntityRatingService.grade(score) == "A"
    assert MatrixReferenceRatingService.grade(score, Decimal("86.675")) == "BB"
    assert "escala dinámica" in RatingScoreAuditService.CRITERION_WARNING
    assert "FIJA" in RatingScoreAuditService.CRITERION_WARNING


def test_fixed_document_threshold_boundaries_are_not_cohort_dependent() -> None:
    expected = (
        ("73.320", "AA"),
        ("73.319", "A"),
        ("64.690", "A"),
        ("64.680", "BB"),
        ("56.067", "BB"),
        ("56.066", "B"),
        ("47.442", "B"),
        ("47.441", "CC"),
    )
    for raw, grade in expected:
        assert FinancialEntityRatingService.grade(Decimal(raw)) == grade


def test_document_rounds_each_profitability_weight_to_667_percent() -> None:
    definition = {
        indicator.code: indicator for indicator in FinancialEntityRatingService.INDICATORS
    }
    profitability = ("MARGIN_INTERMEDIATION", "ROA", "ROE")
    assert all(
        definition[code].weight_percent == Decimal("20") / Decimal("3") for code in profitability
    )
    assert Decimal("6.67") * 3 == Decimal("20.01")
    assert Decimal("20") != Decimal("6.67") * 3


def test_binary_documentation_conflict_is_never_silently_resolved() -> None:
    warning = RatingScoreAuditService.CRITERION_WARNING
    assert "sección 3.6.1" in warning
    assert "4.3" in warning
    assert "contradicción" in warning
    assert "5 puntos" in warning
