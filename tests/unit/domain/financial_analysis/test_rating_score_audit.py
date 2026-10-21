"""Pruebas de regresión para conciliación 08ME14-01 sin modificar el score."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    RatingDirection,
    RatingLevel,
)
from aip.domain.financial_analysis.rating_score_audit import RatingScoreAuditService
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService

CUTOFF = date(2026, 9, 30)


def _coopenae_rating():
    """Universo sintético para reproducir solo los niveles visibles en pantalla."""
    factors = {
        "MARGIN_INTERMEDIATION": Decimal("0.75"),
        "ROA": Decimal("0.50"),
        "ROE": Decimal("0.75"),
        "CURRENT_PORTFOLIO": Decimal("0.75"),
        "COVERAGE_ARREARS": Decimal("0.75"),
        "DELINQUENCY_90": Decimal("0.50"),
        "OPERATING_EFFICIENCY": Decimal("0.75"),
        "ADMIN_EXPENSE_ASSETS": Decimal("0.75"),
        "EQUITY_COMMITMENT": Decimal("0.50"),
        "CAPITAL_ADEQUACY": Decimal("0.50"),
        "LIQUIDITY_COVERAGE": Decimal("0.50"),
    }
    entities = tuple(FinancialEntity(str(i), f"Entidad {i}") for i in range(5))
    lines = []
    for definition in FinancialEntityRatingService.INDICATORS:
        if definition.direction is RatingDirection.BINARY:
            values = (Decimal("0"), Decimal("0"), Decimal("1"), Decimal("0"), Decimal("1"))
        else:
            direction = definition.direction
            factor = factors[definition.code]
            selected_value = {
                RatingDirection.HIGHER_IS_BETTER: {
                    Decimal("0.75"): Decimal("4"),
                    Decimal("0.50"): Decimal("2"),
                },
                RatingDirection.LOWER_IS_BETTER: {
                    Decimal("0.75"): Decimal("2"),
                    Decimal("0.50"): Decimal("4"),
                },
            }[direction][factor]
            values = (selected_value,) + tuple(
                x for x in map(Decimal, ("1", "2", "3", "4", "5")) if x != selected_value
            )
        for entity, value in zip(entities, values, strict=True):
            lines.append(
                FinancialStatementLine(
                    entity=entity,
                    statement_date=CUTOFF,
                    statement_type=FinancialStatementType.INDICATORS,
                    account_code=definition.code,
                    account_name=definition.aliases[0],
                    amount=value,
                )
            )
    return FinancialEntityRatingService().evaluate(
        tuple(lines), selected_entity_id="0", cutoff_date=CUTOFF
    )


def test_capture_coopenae_score_and_binary_sensitivity() -> None:
    rating = _coopenae_rating()
    assert rating.score == Decimal("60.833")
    assert rating.grade == "BB"
    audit = RatingScoreAuditService.audit(rating)
    assert audit.status == "CUADRA"
    assert audit.recomputed_score == rating.score
    assert audit.recomputed_grade == "BB"
    assert len(audit.rows) == 13
    assert not audit.issues
    assert rating.score == Decimal("60.833")  # Auditoría de solo lectura.


def test_audit_detects_score_level_and_contribution_discrepancies() -> None:
    rating = _coopenae_rating()
    bad_score = RatingScoreAuditService.audit(replace(rating, score=Decimal("61")))
    assert bad_score.status == "REVISAR"
    assert any("global" in issue for issue in bad_score.issues)

    changed = replace(
        rating.indicators[0],
        level=RatingLevel.OUTSTANDING,
        contribution=rating.indicators[0].contribution + Decimal("1"),
    )
    tampered_rating = replace(rating, indicators=(changed, *rating.indicators[1:]))
    audit = RatingScoreAuditService.audit(tampered_rating)
    assert audit.status == "REVISAR"
    assert audit.rows[0].status == "REVISAR"


def test_incomplete_rating_does_not_invent_scores_or_alternatives() -> None:
    rating = _coopenae_rating()
    incomplete = replace(
        rating, status="INCOMPLETE", score=None, grade=None, indicators=rating.indicators[:-1]
    )
    audit = RatingScoreAuditService.audit(incomplete)
    assert audit.status == "REVISAR"  # Contrato de 13 indicadores roto.
    assert audit.recomputed_score is None
    assert audit.recomputed_grade is None


def test_p15_p85_exact_boundaries_respect_certified_comparisons() -> None:
    rating = _coopenae_rating()
    higher = next(x for x in rating.indicators if x.code == "ROA")
    definition = next(x for x in FinancialEntityRatingService.INDICATORS if x.code == "ROA")
    for value, expected in (
        (higher.percentile_15, RatingLevel.CRITICAL),
        (higher.midpoint, RatingLevel.IMPROVABLE),
        (higher.percentile_85, RatingLevel.SATISFACTORY),
    ):
        input_row = replace(higher, value=value)
        actual, factor, _rule = RatingScoreAuditService._recalculate(input_row, definition)
        assert actual is expected
        assert factor is not None


def test_binary_guarantee_and_supervision_have_distinct_favorable_values() -> None:
    rating = _coopenae_rating()
    audit = RatingScoreAuditService.audit(rating)
    by_code = {row.code: row for row in audit.rows}
    assert by_code["PROPORTIONAL_SUPERVISION"].expected == Decimal("5")
    assert by_code["STATE_GUARANTEE"].expected == Decimal("0")
    assert "Conciliación de codificación" in audit.criterion_warning
