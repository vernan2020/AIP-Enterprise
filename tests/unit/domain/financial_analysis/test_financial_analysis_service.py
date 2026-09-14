from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.domain.financial_analysis.services import FinancialAnalysisService


def _line(
    entity: FinancialEntity,
    cutoff: date,
    name: str,
    amount: str,
    statement_type: FinancialStatementType = FinancialStatementType.BALANCE_SHEET,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=entity,
        statement_date=cutoff,
        statement_type=statement_type,
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
        _line(
            coopealianza,
            cutoff,
            "RESULTADO DEL PERIODO",
            "8000000000",
            FinancialStatementType.INCOME_STATEMENT,
        ),
        _line(
            coopealianza,
            cutoff,
            "ROA",
            "1.25",
            FinancialStatementType.INDICATORS,
        ),
        _line(coopealianza, previous, "TOTAL ACTIVO", "800000000000"),
        _line(peer, cutoff, "TOTAL ACTIVO", "300000000000"),
    )

    snapshot = FinancialAnalysisService().build_snapshot(lines, cutoff_date=cutoff)

    assert snapshot.status == "AVAILABLE"
    assert snapshot.selected_entity == coopealianza
    assert len(snapshot.peer_summaries) == 2
    assert len(snapshot.peer_ratings) == 2
    assert {item.entity.entity_id for item in snapshot.peer_ratings} == {"7", "8"}
    assert all(item.total_indicators == 13 for item in snapshot.peer_ratings)
    assert all(item.status == "INCOMPLETE" for item in snapshot.peer_ratings)
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


def test_snapshot_exposes_all_selected_entity_series_and_additive_market_composition() -> None:
    selected = FinancialEntity("7", "Coopealianza R.L.", "Cooperativas")
    peer = FinancialEntity("8", "Otra entidad", "Cooperativas")
    current = date(2026, 7, 31)
    previous = date(2026, 6, 30)
    lines = (
        _line(selected, previous, "TOTAL ACTIVO", "600"),
        _line(selected, previous, "DISPONIBILIDADES", "80"),
        _line(
            selected,
            previous,
            "INDICADOR DE PRUEBA",
            "0.11",
            FinancialStatementType.INDICATORS,
        ),
        _line(selected, current, "TOTAL ACTIVO", "750"),
        _line(selected, current, "DISPONIBILIDADES", "100"),
        _line(
            selected,
            current,
            "RESULTADO DEL PERIODO",
            "20",
            FinancialStatementType.INCOME_STATEMENT,
        ),
        _line(
            selected,
            current,
            "INDICADOR DE PRUEBA",
            "0.12",
            FinancialStatementType.INDICATORS,
        ),
        _line(peer, current, "TOTAL ACTIVO", "250"),
        _line(
            peer,
            current,
            "RESULTADO DEL PERIODO",
            "10",
            FinancialStatementType.INCOME_STATEMENT,
        ),
    )

    snapshot = FinancialAnalysisService().build_snapshot(
        lines,
        selected_entity_id=selected.entity_id,
        cutoff_date=current,
    )

    history_by_source = {series.source_account: series for series in snapshot.statement_history}
    assert "DISP" in history_by_source
    assert tuple(point.value for point in history_by_source["DISP"].points) == (
        Decimal("80"),
        Decimal("100"),
    )
    assert history_by_source["INDI"].unit == "PERCENT"
    assert tuple(point.value for point in history_by_source["INDI"].points) == (
        Decimal("11.00"),
        Decimal("12.00"),
    )

    market_assets = next(
        series for series in snapshot.market_composition if series.code == "MARKET_ASSETS"
    )
    shares = {point.entity.entity_id: point.share_percent for point in market_assets.points}
    assert shares == {"7": Decimal("75.00"), "8": Decimal("25.00")}
    assert sum(shares.values(), Decimal("0")) == Decimal("100.00")
