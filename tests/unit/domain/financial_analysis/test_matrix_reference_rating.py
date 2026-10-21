"""Regression tests for the Excel-validated monthly score profile."""

from __future__ import annotations

from decimal import Decimal

import pytest

from aip.domain.financial_analysis.matrix_reference_rating import (
    MatrixEntityInput,
    MatrixReferenceRatingService,
)
from aip.domain.financial_analysis.models import RatingDirection
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService


def _entity(index: int, *, liquidity: bool = True) -> MatrixEntityInput:
    values = {}
    for definition in FinancialEntityRatingService.INDICATORS:
        if definition.direction is RatingDirection.BINARY:
            continue
        if definition.code in {"ROA", "ROE"}:
            value = (
                Decimal("-0.04"),
                Decimal("-0.02"),
                Decimal("0.01"),
                Decimal("0.03"),
            )[index]
        else:
            value = Decimal(index + 1) / Decimal("10")
        values[definition.code] = value
    if not liquidity:
        values["LIQUIDITY_COVERAGE"] = None
    return MatrixEntityInput(
        entity_id=str(index),
        name=f"Entidad {index}",
        indicators=values,
        regulation_full=index != 1,
        state_guarantee=index == 0,
    )


def test_reference_floors_negative_roa_and_roe_p15_to_zero() -> None:
    result = MatrixReferenceRatingService.evaluate(tuple(_entity(i) for i in range(4)))
    assert result.peer_counts["ROA"] == 4
    assert result.lower_cutoffs["ROA"] == Decimal("0")
    assert result.lower_cutoffs["ROE"] == Decimal("0")
    assert result.score_maximum is not None
    assert all(item.status == "COMPLETE" for item in result.entities)


def test_reference_explicit_profitability_weights_are_667_not_20_divided_by_3() -> None:
    result = MatrixReferenceRatingService.evaluate(tuple(_entity(i) for i in range(4)))
    weights = {row.code: row.weight for row in result.entities[0].indicators}
    assert weights["MARGIN_INTERMEDIATION"] == Decimal("6.67")
    assert weights["ROA"] == Decimal("6.67")
    assert weights["ROE"] == Decimal("6.67")
    assert sum(weights.values(), start=Decimal("0")) == Decimal("100.01")


@pytest.mark.parametrize(
    ("score", "expected"),
    (
        ("86.6750", "AA"),
        ("73.5500", "A"),
        ("66.8825", "A"),
        ("64.7975", "BB"),
        ("46.0450", "CC"),
    ),
)
def test_reference_classification_depends_on_monthly_maximum(score: str, expected: str) -> None:
    assert MatrixReferenceRatingService.grade(Decimal(score), Decimal("86.675")) == expected


def test_missing_liquidity_must_not_receive_unapproved_full_points() -> None:
    cohort = tuple(_entity(i, liquidity=i != 0) for i in range(4))
    missing = MatrixReferenceRatingService.evaluate(cohort)
    assert missing.entities[0].status == "INCOMPLETE"
    assert missing.entities[0].score is None
    assert "LIQUIDITY_COVERAGE" in missing.entities[0].missing

    documented = MatrixReferenceRatingService.evaluate(
        cohort, documented_liquidity_exceptions=frozenset({"0"})
    )
    row = next(
        item for item in documented.entities[0].indicators if item.code == "LIQUIDITY_COVERAGE"
    )
    assert row.contribution == Decimal("10")
    assert row.origin == "EXCEPCION_EXCEL_DOCUMENTADA"
    assert documented.entities[0].status == "COMPLETE"


def test_duplicate_entities_and_orphan_overrides_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicados"):
        MatrixReferenceRatingService.evaluate((_entity(0), _entity(0)))
    with pytest.raises(ValueError, match="ajena"):
        MatrixReferenceRatingService.evaluate(
            (_entity(0), _entity(1), _entity(2)),
            documented_liquidity_exceptions=frozenset({"no-existe"}),
        )


def test_insufficient_peers_do_not_generate_fictitious_scoring() -> None:
    rating = MatrixReferenceRatingService.evaluate((_entity(0), _entity(1)))
    assert rating.score_maximum is None
    assert all(entity.score is None for entity in rating.entities)
    assert all(entity.grade is None for entity in rating.entities)


def test_incomplete_cohort_suspends_every_letter_and_monthly_maximum() -> None:
    from dataclasses import replace

    entities = tuple(replace(_entity(i % 4), entity_id=str(i)) for i in range(38))
    complete = MatrixReferenceRatingService.evaluate(entities, required_cohort_size=38)
    assert complete.classification_status == "APTA"
    assert complete.expected_cohort_size == 38
    assert complete.score_maximum is not None
    assert all(item.grade is not None for item in complete.entities)

    short = MatrixReferenceRatingService.evaluate(entities[:-1], required_cohort_size=38)
    assert short.classification_status == "COHORTE_INCOMPLETA"
    assert short.score_maximum is None
    assert all(item.grade is None for item in short.entities)
    assert any(item.score is not None for item in short.entities)

    with_missing_liquidity = tuple(
        (
            replace(item, indicators={**item.indicators, "LIQUIDITY_COVERAGE": None})
            if item.entity_id == "0"
            else item
        )
        for item in entities
    )
    incomplete = MatrixReferenceRatingService.evaluate(
        with_missing_liquidity, required_cohort_size=38
    )
    assert incomplete.classification_status == "INDICADORES_INCOMPLETOS"
    assert incomplete.score_maximum is None
    assert all(item.grade is None for item in incomplete.entities)
    assert incomplete.incomplete_entities == ("0",)


def test_reference_cohort_size_parameter_is_strictly_checked() -> None:
    with pytest.raises(ValueError, match="incompatible"):
        MatrixReferenceRatingService.evaluate((_entity(0),), required_cohort_size=2)
    with pytest.raises(ValueError, match="más entidades"):
        MatrixReferenceRatingService.evaluate(
            tuple(_entity(i) for i in range(4)), required_cohort_size=3
        )
