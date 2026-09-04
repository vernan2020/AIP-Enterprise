from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.institutional_flags import InstitutionalEntityFlagService
from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)


def _base(entity: FinancialEntity) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=entity,
        statement_date=date(2026, 7, 31),
        statement_type=FinancialStatementType.BALANCE_SHEET,
        account_code="10000",
        account_name="ACTIVO TOTAL",
        amount=Decimal("1"),
    )


def test_controlled_flags_cover_state_guarantee_and_proportional_supervision() -> None:
    entities = (
        FinancialEntity("1", "Banco Nacional de Costa Rica", "Bancos"),
        FinancialEntity("2", "Mutual Cartago de Ahorro y Préstamo", "Mutuales"),
        FinancialEntity("3", "COOPEMEDICOS R.L.", "Cooperativas"),
        FinancialEntity("4", "COOPEUNA", "Cooperativas"),
        FinancialEntity("5", "COOPEALIANZA R.L.", "Cooperativas"),
    )

    result = InstitutionalEntityFlagService().augment(
        tuple(_base(entity) for entity in entities),
        cutoff_date=date(2026, 7, 31),
    )
    flags = {
        (line.entity.entity_id, line.account_code): line.amount
        for line in result
        if line.statement_type is FinancialStatementType.INDICATORS
    }

    assert flags[("1", "CALC:STATE_GUARANTEE")] == Decimal("1")
    assert flags[("2", "CALC:STATE_GUARANTEE")] == Decimal("1")
    assert flags[("3", "CALC:PROPORTIONAL_SUPERVISION")] == Decimal("1")
    assert flags[("4", "CALC:PROPORTIONAL_SUPERVISION")] == Decimal("1")
    assert flags[("5", "CALC:STATE_GUARANTEE")] == Decimal("0")
    assert flags[("5", "CALC:PROPORTIONAL_SUPERVISION")] == Decimal("0")
