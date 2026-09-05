from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    RatingDirection,
    SourceTrace,
)
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService

CUTOFF = date(2026, 6, 30)


def _line(entity: FinancialEntity, name: str, value: Decimal) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=entity,
        statement_date=CUTOFF,
        statement_type=FinancialStatementType.INDICATORS,
        account_code=name[:12],
        account_name=name,
        amount=value,
    )


def _cohort(*, selected_factors: dict[str, Decimal]) -> tuple[FinancialStatementLine, ...]:
    entities = tuple(FinancialEntity(str(index), f"Entidad {index}") for index in range(5))
    lines: list[FinancialStatementLine] = []
    factor_to_value = {
        RatingDirection.HIGHER_IS_BETTER: {
            Decimal("1"): Decimal("5"),
            Decimal("0.75"): Decimal("4"),
            Decimal("0.50"): Decimal("2"),
            Decimal("0.25"): Decimal("1"),
        },
        RatingDirection.LOWER_IS_BETTER: {
            Decimal("1"): Decimal("1"),
            Decimal("0.75"): Decimal("2"),
            Decimal("0.50"): Decimal("4"),
            Decimal("0.25"): Decimal("5"),
        },
    }
    for definition in FinancialEntityRatingService.INDICATORS:
        name = definition.aliases[0]
        if definition.direction is RatingDirection.BINARY:
            selected_value = selected_factors[definition.code]
            values = (selected_value, Decimal("0"), Decimal("1"), Decimal("0"), Decimal("1"))
        else:
            factor = selected_factors[definition.code]
            selected_value = factor_to_value[definition.direction][factor]
            values = (selected_value,) + tuple(
                value
                for value in map(Decimal, ("1", "2", "3", "4", "5"))
                if value != selected_value
            )
        for entity, value in zip(entities, values, strict=True):
            lines.append(_line(entity, name, value))
    return tuple(lines)


def test_official_methodology_can_reach_full_score() -> None:
    factors = {
        definition.code: Decimal("1") for definition in FinancialEntityRatingService.INDICATORS
    }

    rating = FinancialEntityRatingService().evaluate(
        _cohort(selected_factors=factors),
        selected_entity_id="0",
        cutoff_date=CUTOFF,
    )

    assert rating.status == "COMPLETE"
    assert rating.score == Decimal("100.000")
    assert rating.grade == "AA"
    assert rating.coverage_percent == Decimal("100.00")
    assert sum(item.weight_percent for item in rating.indicators) == pytest.approx(Decimal("100"))


def test_reference_coopealianza_profile_is_reweighted_with_word_policy() -> None:
    factors = {
        "MARGIN_INTERMEDIATION": Decimal("1"),
        "ROA": Decimal("0.75"),
        "ROE": Decimal("0.75"),
        "CURRENT_PORTFOLIO": Decimal("0.50"),
        "COVERAGE_ARREARS": Decimal("1"),
        "DELINQUENCY_90": Decimal("0.50"),
        "OPERATING_EFFICIENCY": Decimal("1"),
        "ADMIN_EXPENSE_ASSETS": Decimal("0.75"),
        "EQUITY_COMMITMENT": Decimal("1"),
        "CAPITAL_ADEQUACY": Decimal("0.50"),
        "LIQUIDITY_COVERAGE": Decimal("1"),
        "PROPORTIONAL_SUPERVISION": Decimal("1"),
        "STATE_GUARANTEE": Decimal("0"),
    }

    rating = FinancialEntityRatingService().evaluate(
        _cohort(selected_factors=factors),
        selected_entity_id="0",
        cutoff_date=CUTOFF,
    )

    assert rating.score == Decimal("74.792")
    assert rating.grade == "AA"
    assert {item.name: item.weight_percent for item in rating.dimensions} == {
        "Rentabilidad": Decimal("20"),
        "Calidad de la Cartera": Decimal("25"),
        "Desempeño Operativo": Decimal("15"),
        "Solvencia": Decimal("20"),
        "Liquidez": Decimal("10"),
        "Supervisión proporcional": Decimal("10"),
    }


@pytest.mark.parametrize(
    ("score", "grade"),
    (
        ("73.320", "AA"),
        ("73.319", "A"),
        ("64.690", "A"),
        ("56.067", "BB"),
        ("47.442", "B"),
        ("47.441", "CC"),
    ),
)
def test_official_grade_boundaries(score: str, grade: str) -> None:
    assert FinancialEntityRatingService.grade(Decimal(score)) == grade


def test_rating_is_not_emitted_when_an_official_indicator_is_missing() -> None:
    factors = {
        definition.code: Decimal("1") for definition in FinancialEntityRatingService.INDICATORS
    }
    lines = tuple(
        line
        for line in _cohort(selected_factors=factors)
        if line.account_name != "GARANTIA DEL ESTADO"
    )

    rating = FinancialEntityRatingService().evaluate(
        lines,
        selected_entity_id="0",
        cutoff_date=CUTOFF,
    )

    assert rating.status == "INCOMPLETE"
    assert rating.score is None
    assert rating.grade is None
    assert rating.coverage_percent == Decimal("92.31")
    assert "13 indicadores" in rating.diagnostics[0]


def test_non_methodological_current_portfolio_proxy_is_ignored() -> None:
    entity = FinancialEntity("0", "Entidad 0")
    exact = _line(entity, "Cartera de crédito al día", Decimal("0.10"))
    proxy = FinancialStatementLine(
        entity=entity,
        statement_date=CUTOFF,
        statement_type=FinancialStatementType.INDICATORS,
        account_code="63000",
        account_name="Cartera al día y con atraso hasta 90 días/Cartera total",
        amount=Decimal("0.96"),
        trace=SourceTrace(
            source_name="SUGEF - API pública de Información Financiera Contable",
            source_url="https://www.sugef.fi.cr",
            file_path="api",
            sheet_name="indicadores",
            row_number=1,
        ),
    )
    definition = next(
        item for item in FinancialEntityRatingService.INDICATORS if item.code == "CURRENT_PORTFOLIO"
    )

    selected = FinancialEntityRatingService._find_indicator((exact, proxy), definition)

    assert selected is exact
