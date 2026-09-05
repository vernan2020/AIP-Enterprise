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


def test_extended_official_names_and_accents_are_normalized() -> None:
    assert _flag("Banco Nacional de Costa Rica", "CALC:STATE_GUARANTEE") == Decimal("1")
    assert (
        _flag("Mutual Cartago de Ahorro y Préstamo", "CALC:STATE_GUARANTEE")
        == Decimal("1")
    )


def test_unlisted_entity_receives_zero_for_both_binary_flags() -> None:
    assert _flag("COOPEALIANZA R.L.", "CALC:STATE_GUARANTEE") == Decimal("0")
    assert _flag("COOPEALIANZA R.L.", "CALC:PROPORTIONAL_SUPERVISION") == Decimal("0")
