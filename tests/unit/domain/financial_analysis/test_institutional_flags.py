from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.financial_analysis.institutional_flags import InstitutionalEntityFlagService
from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService

_CUTOFF = date(2026, 7, 31)
_STATE_GUARANTEE_ENTITIES = (
    "Banco Nacional",
    "Banco de Costa Rica",
    "Banco Popular",
    "Mutual Alajuela",
    "Mutual Cartago",
)
_PROPORTIONAL_SUPERVISION_ENTITIES = (
    "COOPAVEGRA R.L.",
    "COOPE EMPLEADOS AYA R.L.",
    "COOPE SAN MARCOS R.L.",
    "COOPEBANPO R.L.",
    "COOPECAR R.L.",
    "COOPEFYL R.L.",
    "COOPEGRECIA R.L.",
    "COOPEJUDICIALES R.L.",
    "COOPEMEDICOS R.L.",
    "COOPESANRAMON R.L.",
    "COOPEUNA",
    "CREDECOOP R.L.",
)
_RUNTIME_STATE_GUARANTEE_NAMES = (
    "BANCO DE COSTA RICA – Banco de Costa Rica",
    "BANCO POPULAR – Banco Popular y de Desarrollo Comunal",
    "BANCO NACIONAL – Banco Nacional de Costa Rica",
    "GRUPO MUTUAL – Mutual Alajuela de Ahorro y Préstamo",
    "MUCAP – Mutual Cartago de Ahorro y Préstamo",
)
_RUNTIME_PROPORTIONAL_NAMES = (
    "COOPEAYA – COOPE EMPLEADOS AYA R.L.",
    "COOPESANMARCOS – COOPE SAN MARCOS R.L.",
    "COOPECAR R.L. – Cooperativa de Ahorro y Crédito",
)


def _base(entity: FinancialEntity) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=entity,
        statement_date=_CUTOFF,
        statement_type=FinancialStatementType.BALANCE_SHEET,
        account_code="10000",
        account_name="ACTIVO TOTAL",
        amount=Decimal("1"),
    )


def _flag(entity_name: str, account_code: str) -> Decimal:
    entity = FinancialEntity("TEST", entity_name, "Prueba")
    result = InstitutionalEntityFlagService().augment(
        (_base(entity),),
        cutoff_date=_CUTOFF,
    )
    return next(line.amount for line in result if line.account_code == account_code)


@pytest.mark.parametrize("entity_name", _STATE_GUARANTEE_ENTITIES)
def test_every_controlled_state_guarantee_entity_is_flagged(entity_name: str) -> None:
    assert _flag(entity_name, "CALC:STATE_GUARANTEE") == Decimal("1")


@pytest.mark.parametrize("entity_name", _PROPORTIONAL_SUPERVISION_ENTITIES)
def test_every_controlled_proportional_supervision_entity_is_flagged(entity_name: str) -> None:
    assert _flag(entity_name, "CALC:PROPORTIONAL_SUPERVISION") == Decimal("1")


@pytest.mark.parametrize("entity_name", _RUNTIME_STATE_GUARANTEE_NAMES)
def test_runtime_composite_state_guarantee_names_are_flagged(entity_name: str) -> None:
    assert _flag(entity_name, "CALC:STATE_GUARANTEE") == Decimal("1")


@pytest.mark.parametrize("entity_name", _RUNTIME_PROPORTIONAL_NAMES)
def test_runtime_composite_proportional_names_are_flagged(entity_name: str) -> None:
    assert _flag(entity_name, "CALC:PROPORTIONAL_SUPERVISION") == Decimal("1")


def test_extended_official_names_and_accents_are_normalized() -> None:
    assert _flag("Banco Nacional de Costa Rica", "CALC:STATE_GUARANTEE") == Decimal("1")
    assert _flag("Mutual Cartago de Ahorro y Préstamo", "CALC:STATE_GUARANTEE") == Decimal("1")


def test_unlisted_entity_receives_zero_for_both_binary_flags() -> None:
    assert _flag("COOPEALIANZA R.L.", "CALC:STATE_GUARANTEE") == Decimal("0")
    assert _flag("COOPEALIANZA R.L.", "CALC:PROPORTIONAL_SUPERVISION") == Decimal("0")


def test_runtime_composite_unlisted_entity_remains_unflagged() -> None:
    name = "COOPEALIANZA – Cooperativa de Ahorro y Crédito Alianza de Pérez Zeledón R.L."
    assert _flag(name, "CALC:STATE_GUARANTEE") == Decimal("0")
    assert _flag(name, "CALC:PROPORTIONAL_SUPERVISION") == Decimal("0")


def test_bcr_runtime_name_receives_full_binary_dimension_score() -> None:
    entity = FinancialEntity("BCR", "BANCO DE COSTA RICA – Banco de Costa Rica", "Banco")
    lines = InstitutionalEntityFlagService().augment(
        (_base(entity),),
        cutoff_date=_CUTOFF,
    )

    rating = FinancialEntityRatingService().evaluate(
        lines,
        selected_entity_id=entity.entity_id,
        cutoff_date=_CUTOFF,
    )

    proportional = next(
        item for item in rating.indicators if item.code == "PROPORTIONAL_SUPERVISION"
    )
    guarantee = next(item for item in rating.indicators if item.code == "STATE_GUARANTEE")
    dimension = next(
        item for item in rating.dimensions if item.name == "Supervisión proporcional"
    )

    assert proportional.value == Decimal("0")
    assert proportional.contribution == Decimal("5")
    assert guarantee.value == Decimal("1")
    assert guarantee.contribution == Decimal("5")
    assert dimension.score == Decimal("10.000")
