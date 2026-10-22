"""Reconciliation must catch wrong source cohorts even when scoring still sums."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    RatingDirection,
)
from aip.domain.financial_analysis.normative_source_audit import (
    NormativeSourcePercentileAuditor,
)
from aip.domain.financial_analysis.sugef_ratings import (
    SUGEFOnlyFinancialEntityRatingService,
)


def _source_data() -> tuple[FinancialStatementLine, ...]:
    service = SUGEFOnlyFinancialEntityRatingService()
    records = []
    for i in range(4):
        entity = FinancialEntity(str(i), f"Entidad {i}")
        for definition in service.INDICATORS:
            if definition.code == "ROA":
                continue  # Historical accounting unavailable: canonical ROA stays absent.
            if definition.direction is RatingDirection.BINARY:
                value = (
                    Decimal("0") if definition.code == "PROPORTIONAL_SUPERVISION" else Decimal("1")
                )
            else:
                value = Decimal(i + 1) / Decimal("100")
            records.append(
                FinancialStatementLine(
                    entity=entity,
                    statement_date=date(2026, 9, 30),
                    statement_type=FinancialStatementType.INDICATORS,
                    account_code=definition.code,
                    account_name=definition.aliases[0],
                    amount=value,
                )
            )
    return tuple(records)


def test_source_reconciliation_agrees_with_actual_peer_population() -> None:
    source = _source_data()
    rating = SUGEFOnlyFinancialEntityRatingService().evaluate(
        source, selected_entity_id="0", cutoff_date=date(2026, 9, 30)
    )
    audit = NormativeSourcePercentileAuditor.audit(source, entity_id="0", rating=rating)
    assert audit.status == "CUADRA"
    assert not audit.discrepancies
    assert len(audit.rows) == 13
    assert next(row for row in audit.rows if row.code == "ROE").observed_peers == 4
    assert next(row for row in audit.rows if row.code == "ROA").observed_p15 is None


def test_audit_detects_wrong_percentiles_even_when_total_score_is_unchanged() -> None:
    source = _source_data()
    rating = SUGEFOnlyFinancialEntityRatingService().evaluate(
        source, selected_entity_id="0", cutoff_date=date(2026, 9, 30)
    )
    index = next(i for i, row in enumerate(rating.indicators) if row.code == "ROE")
    original = rating.indicators[index]
    changed = replace(
        original,
        percentile_15=original.percentile_15 + Decimal("0.002"),
        peer_count=original.peer_count - 1,
    )
    new_items = (*rating.indicators[:index], changed, *rating.indicators[index + 1 :])
    report = NormativeSourcePercentileAuditor.audit(
        source, entity_id="0", rating=replace(rating, indicators=new_items)
    )
    assert report.status == "REVISAR"
    assert any(
        "ROE" in issue and "P15" in issue and "pares" in issue for issue in report.discrepancies
    )


def test_source_audit_identifies_missing_peer_in_selected_cutoff() -> None:
    source = _source_data()
    rating = SUGEFOnlyFinancialEntityRatingService().evaluate(
        source, selected_entity_id="0", cutoff_date=date(2026, 9, 30)
    )
    incomplete_source = tuple(
        row for row in source if not (row.entity.entity_id == "3" and row.account_code == "ROE")
    )
    report = NormativeSourcePercentileAuditor.audit(incomplete_source, entity_id="0", rating=rating)
    assert report.status == "REVISAR"
    assert any("ROE" in issue and "pares" in issue for issue in report.discrepancies)
