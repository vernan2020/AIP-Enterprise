"""Guard the approved 08ME14-01 V01 parameters against accidental UI-driven changes."""

from __future__ import annotations

from decimal import Decimal

from aip.domain.financial_analysis.models import RatingDirection
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService
from aip.domain.financial_analysis.sugef_ratings import SUGEFOnlyFinancialEntityRatingService


def test_internal_rating_weights_and_13_indicator_contract() -> None:
    service = FinancialEntityRatingService
    assert service.METHODOLOGY_CODE == "08ME14-01"
    assert "27/06/2025" in service.METHODOLOGY_VERSION
    assert service.MINIMUM_PEERS == 3
    assert len(service.INDICATORS) == 13
    assert sum((item.weight_percent for item in service.INDICATORS), Decimal("0")) == 100
    assert dict(service.DIMENSION_WEIGHTS) == {
        "Rentabilidad": Decimal("20"),
        "Calidad de la Cartera": Decimal("25"),
        "Desempeño Operativo": Decimal("15"),
        "Solvencia": Decimal("20"),
        "Liquidez": Decimal("10"),
        "Supervisión proporcional": Decimal("10"),
    }
    for dimension, weight in service.DIMENSION_WEIGHTS:
        assert (
            sum(
                (item.weight_percent for item in service.INDICATORS if item.dimension == dimension),
                Decimal("0"),
            )
            == weight
        )
    assert {
        item.code for item in service.INDICATORS if item.direction is RatingDirection.BINARY
    } == {
        "PROPORTIONAL_SUPERVISION",
        "STATE_GUARANTEE",
    }


def test_internal_rating_grade_boundaries_preserve_certified_values() -> None:
    grade = SUGEFOnlyFinancialEntityRatingService.grade
    for value, expected in (
        ("73.320", "AA"),
        ("73.319", "A"),
        ("64.690", "A"),
        ("64.689", "BB"),
        ("56.067", "BB"),
        ("56.066", "B"),
        ("47.442", "B"),
        ("47.441", "CC"),
    ):
        assert grade(Decimal(value)) == expected


def test_internal_rating_uses_p15_p85_and_explicit_binary_favorable_flags() -> None:
    service = FinancialEntityRatingService
    assert {
        item.code: item.binary_favorable_value
        for item in service.INDICATORS
        if item.direction is RatingDirection.BINARY
    } == {
        "PROPORTIONAL_SUPERVISION": Decimal("0"),
        "STATE_GUARANTEE": Decimal("1"),
    }
    assert service._percentile(
        (Decimal("0"), Decimal("50"), Decimal("100")), Decimal("0.15")
    ) == Decimal("15.0")
    assert service._percentile(
        (Decimal("0"), Decimal("50"), Decimal("100")), Decimal("0.85")
    ) == Decimal("85.0")
