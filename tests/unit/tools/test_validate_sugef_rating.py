from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    EntityFinancialRating,
    FinancialAnalysisSnapshot,
    FinancialEntity,
    FinancialIndicatorReconciliation,
    FinancialIndicatorReconciliationStatus,
    RatingDirection,
    RatingIndicatorAssessment,
    RatingLevel,
)
from aip.tools.validate_sugef_rating import _payload, main


def test_payload_preserves_decimal_precision_and_reconciliation() -> None:
    entity = FinancialEntity("3004045138", "COOPEALIANZA R.L.", "Cooperativas")
    indicator = RatingIndicatorAssessment(
        code="ROA",
        label="ROA",
        dimension="Rentabilidad",
        direction=RatingDirection.HIGHER_IS_BETTER,
        weight_percent=Decimal("6.6666666667"),
        value=Decimal("0.01038"),
        percentile_15=Decimal("0.001"),
        midpoint=Decimal("0.012"),
        percentile_85=Decimal("0.025"),
        level=RatingLevel.SATISFACTORY,
        contribution=Decimal("5.000"),
        peer_count=43,
        source_account="ROA · SUGEF API pública",
    )
    rating = EntityFinancialRating(
        status="COMPLETE",
        methodology_code="08ME14-01",
        methodology_version="V01",
        effective_date=date(2026, 7, 31),
        score=Decimal("74.792"),
        grade="AA",
        coverage_percent=Decimal("100.00"),
        indicators=(indicator,),
    )
    reconciliation = FinancialIndicatorReconciliation(
        code="ROA",
        label="ROA",
        published_value=Decimal("0.01038"),
        calculated_value=Decimal("0.01037"),
        difference=Decimal("-0.00001"),
        tolerance=Decimal("0.0001"),
        status=FinancialIndicatorReconciliationStatus.TOLERANCE,
        published_source="SUGEF API pública",
        calculated_source="Cálculo 08ME14-01",
    )
    snapshot = FinancialAnalysisSnapshot(
        status="AVAILABLE",
        cutoff_date=date(2026, 7, 31),
        selected_entity=entity,
        entities=(entity,),
        rating=rating,
        indicator_reconciliations=(reconciliation,),
        source_files=("https://sugef.example/api",),
    )

    payload = _payload(snapshot, date(2026, 8, 31))

    assert payload["requested_cutoff"] == "2026-08-31"
    assert payload["effective_accounting_cutoff"] == "2026-07-31"
    assert payload["rating"]["score"] == "74.792"
    assert payload["rating"]["indicators"][0]["value"] == "0.01038"
    assert payload["reconciliation"][0]["difference"] == "-0.00001"
    assert payload["reconciliation"][0]["status"] == "TOLERANCE"


def test_main_rejects_empty_entity_without_accessing_network(capsys) -> None:
    exit_code = main(["--cutoff", "2026-07-31", "--entity", ""])

    assert exit_code == 1
    assert "--entity no puede estar vacío" in capsys.readouterr().out
