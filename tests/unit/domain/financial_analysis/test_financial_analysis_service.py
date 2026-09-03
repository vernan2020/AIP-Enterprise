from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.domain.financial_analysis.services import FinancialAnalysisService


def _line(entity: FinancialEntity, cutoff: date, name: str, amount: str) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=entity,
        statement_date=cutoff,
        statement_type=FinancialStatementType.BALANCE_SHEET,
        account_code=name[:4],
        account_name=name,
        amount=Decimal(amount),
    )


def test_snapshot_selects_coopealianza_and_builds_peer_comparison() -> None:
    coopealianza = FinancialEntity("7", "Coopealianza R.L.", "Cooperativas")
    peer = FinancialEntity("8", "Otra entidad", "Cooperativas")
    cutoff = date(2026, 7, 31)
    previous = date(2026, 6, 30)
    lines = (
        _line(coopealianza, cutoff, "TOTAL ACTIVO", "810000000000"),
        _line(coopealianza, cutoff, "TOTAL PASIVO", "650000000000"),
        _line(coopealianza, cutoff, "TOTAL PATRIMONIO", "160000000000"),
        _line(coopealianza, cutoff, "RESULTADO DEL PERIODO", "8000000000"),
        _line(coopealianza, cutoff, "ROA", "1.25"),
        _line(coopealianza, previous, "TOTAL ACTIVO", "800000000000"),
        _line(peer, cutoff, "TOTAL ACTIVO", "300000000000"),
    )

    snapshot = FinancialAnalysisService().build_snapshot(lines, cutoff_date=cutoff)

    assert snapshot.status == "AVAILABLE"
    assert snapshot.selected_entity == coopealianza
    assert len(snapshot.peer_summaries) == 2
    by_code = {metric.code: metric for metric in snapshot.metrics}
    assert by_code["ASSETS"].value == Decimal("810000000000")
    assert by_code["ASSETS"].change_percent == Decimal("1.2500")
    assert by_code["ROA"].value == Decimal("1.25")


def test_snapshot_uses_latest_available_date_not_after_requested_cutoff() -> None:
    entity = FinancialEntity("7", "Coopealianza R.L.")
    lines = (
        _line(entity, date(2026, 7, 31), "TOTAL ACTIVO", "810"),
        _line(entity, date(2026, 6, 30), "TOTAL ACTIVO", "800"),
    )

    snapshot = FinancialAnalysisService().build_snapshot(
        lines,
        cutoff_date=date(2026, 7, 15),
    )

    assert snapshot.cutoff_date == date(2026, 6, 30)
    assert snapshot.statement_lines[0].amount == Decimal("800")
