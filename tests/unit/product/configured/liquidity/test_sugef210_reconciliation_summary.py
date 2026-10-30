"""Source-count reporting tests: UI must not invent institutional cash events."""

from __future__ import annotations

from datetime import date

import pytest

from aip.product.configured.liquidity.sugef210_reconciliation_summary import (
    summarize_approved_contractual_source_coverage,
    summarize_contractual_reconciliation,
)

CUTOFF = date(2026, 9, 30)


def test_summary_shows_all_17_reference_windows_without_amounts():
    evidence = {
        "cutoff": CUTOFF.isoformat(),
        "status": "MATCHED_REFERENCE_ONLY",
        "maturity_records": 254198,
        "unique_maturity_rows_matched": 254198,
        "principal_reconciliation": {
            "distinct_contracts_reconciled_exactly": 254161,
            "negative_contracts_matching_signed_band_total": 36,
            "distinct_contracts_with_principal_difference": 1,
        },
        "contract_identities_without_maturity_bands_by_source": {
            "CAPTACIONES": 34046,
            "BORROWING": 13,
        },
        "unbanded_date_evidence_by_sugef210_window": {
            "by_window": {"D01": 33726, "Q01": 1},
            "next_day_concentration_review": {
                "status": "REVIEW_SOURCE_DATE_SEMANTICS",
                "next_day_unbanded_contracts": 33726,
                "future_dated_unbanded_contracts": 33727,
            },
        },
    }
    rows = summarize_contractual_reconciliation(cutoff=CUTOFF, evidence=evidence)
    assert len(rows) == 22
    assert rows[0] == ("Vinculación XML", "REFERENCIA", "254198 de 254198 filas ligadas; sin pagos")
    assert (
        "Fecha corte + 1 día",
        "REVISAR",
        ("33726 de 33727 fechas futuras. No son pagos confirmados."),
    ) in rows
    assert ("Ventana D01", "SOLO FECHAS", "33726 fechas de origen; cero pagos autorizados") in rows
    assert ("Ventana Q01", "SOLO FECHAS", "1 fechas de origen; cero pagos autorizados") in rows
    assert rows[-1][1] == "SIN CERTIFICAR"
    assert "P1" not in str(rows)


def test_summary_rejects_old_cutoff_and_untrusted_private_values():
    with pytest.raises(ValueError, match="cutoff"):
        summarize_contractual_reconciliation(cutoff=CUTOFF, evidence={"cutoff": "2026-08-31"})
    rows = summarize_contractual_reconciliation(
        cutoff=CUTOFF,
        evidence={
            "cutoff": CUTOFF.isoformat(),
            "status": "MATCHED_REFERENCE_ONLY",
            "unique_maturity_rows_matched": "PRIVATE_ACCOUNT",
            "maturity_records": -12,
            "unbanded_date_evidence_by_sugef210_window": {
                "by_window": {"D01": "PRIVATE_AMOUNT"},
            },
        },
    )
    assert len(rows) == 21
    assert "PRIVATE" not in str(rows)
    assert "cero pagos autorizados" in str(rows)


def test_missing_xml_linkage_fails_closed_without_fabricated_zero_rows():
    rows = summarize_contractual_reconciliation(
        cutoff=CUTOFF,
        evidence={"cutoff": CUTOFF.isoformat(), "status": "PARTIAL_SOURCE_COVERAGE"},
    )
    assert len(rows) == 1
    assert rows[0][1] == "NO DISPONIBLE"
    assert "no hay pagos reconocidos" in rows[0][2]


def test_partial_identity_linkage_is_explicitly_marked_for_review():
    rows = summarize_contractual_reconciliation(
        cutoff=CUTOFF,
        evidence={
            "cutoff": CUTOFF.isoformat(),
            "status": "MATCHED_REFERENCE_ONLY",
            "maturity_records": 4,
            "unique_maturity_rows_matched": 3,
            "unmatched_maturity_rows": 1,
        },
    )
    assert rows[0][1] == "REVISAR"
    assert "3 de 4" in rows[0][2]


def test_contractual_coverage_displays_missing_sources_as_unknown_not_zero():
    result = summarize_approved_contractual_source_coverage((("CREDIT", 2, 200),))
    assert tuple(item["source_key"] for item in result) == (
        "CREDIT",
        "CAPTACIONES",
        "BORROWING",
    )
    assert result[0]["approved_contracts"] == 2
    assert result[0]["original_xml_contracts"] == 200
    assert result[0]["unselected_source_records_not_automatically_cashflows"] == 198
    for item in result[1:]:
        assert item["status"] == "NO_APPROVED_CONTRACTUAL_SCHEDULE"
        assert item["approved_contracts"] is None
        assert item["original_xml_contracts"] is None
        assert item["coverage_certified"] is False


def test_contractual_coverage_all_selected_still_not_financially_certified():
    result = summarize_approved_contractual_source_coverage((("CAPTACIONES", 4, 4),))
    assert result[1]["status"] == "ALL_ORIGINAL_ROWS_SELECTED_NOT_FINANCIALLY_CERTIFIED"
    assert result[1]["unselected_source_records_not_automatically_cashflows"] == 0
    assert result[1]["coverage_certified"] is False


@pytest.mark.parametrize(
    "source_rows",
    [
        (("CREDIT", 3, 2),),
        (("CREDIT", -1, 2),),
        (("CREDIT", True, 2),),
        (("CAPTACIONES", 1, 2), ("CAPTACIONES", 1, 2)),
        (("UNSUPPORTED", 1, 1),),
    ],
)
def test_contractual_coverage_rejects_untrusted_denominators(source_rows):
    with pytest.raises(ValueError, match="Invalid original contractual XML source coverage"):
        summarize_approved_contractual_source_coverage(source_rows)
