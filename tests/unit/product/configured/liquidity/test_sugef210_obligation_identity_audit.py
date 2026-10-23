"""Contractual identity crosswalk tests; synthetic identifiers are not AIP data."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaHeader,
    XMLConfiaRecord,
    XMLConfiaResolvedSource,
)
from aip.product.configured.liquidity.sugef210_obligation_identity_audit import (
    audit_obligation_maturity_identity,
)

CUTOFF = date(2026, 9, 30)


class Reader:
    def __init__(self, *, duplicate=False, omit_key=False, wrong_header=False, no_deposits=False):
        self.duplicate = duplicate
        self.omit_key = omit_key
        self.wrong_header = wrong_header
        self.no_deposits = no_deposits

    def resolve_source(self, *, key, cutoff_date):
        assert cutoff_date == CUTOFF
        if self.no_deposits and key == "CAPTACIONES":
            raise FileNotFoundError("source unavailable")
        entity = "OTHER" if self.wrong_header and key == "BORROWING" else "TEST"
        return XMLConfiaResolvedSource(
            key=key,
            path=Path(key + ".xml"),
            header=XMLConfiaHeader("1", key, date(2026, 9, 1), entity, "1", "1"),
        )

    def iter_records(self, source):
        if source.key == "CAPTACIONES":
            values = {
                "IdAcreedor": "P1",
                "IdOperacion": "A1",
                "TipoMonedaObligacion": "1",
                "CuentaContablePrincipal": "211",
            }
            yield XMLConfiaRecord("1", "insertar", values)
            if self.duplicate:
                yield XMLConfiaRecord("2", "insertar", values)
        if source.key == "BORROWING":
            yield XMLConfiaRecord(
                "3",
                "insertar",
                {
                    "IdAcreedor": "P2",
                    "IdOperacion": "A2",
                    "TipoMonedaObligacion": "2",
                    "CuentaContablePrincipal": "220",
                },
            )
        if source.key == "BORROWING_MATURITY":
            rows = (
                {"IdAcreedor": "P1", "IdOperacion": "A1", "SaldoaPagarPrincipal": "200"},
                {"IdAcreedor": "P2", "IdOperacion": "A2", "SaldoaPagarPrincipal": "300"},
                {"IdAcreedor": "P9", "IdOperacion": "A9", "SaldoaPagarPrincipal": "400"},
                {"IdAcreedor": "P1", "IdOperacion": "OTHER", "SaldoaPagarPrincipal": "500"},
            )
            for index, values in enumerate(rows):
                if self.omit_key and index == 1:
                    values = {k: v for k, v in values.items() if k != "IdAcreedor"}
                yield XMLConfiaRecord(str(index), "insertar", values)


def test_identical_composite_only_and_no_cash_from_balances():
    output = audit_obligation_maturity_identity(reader=Reader(), cutoff=CUTOFF)
    assert output["status"] == "MATCHED_REFERENCE_ONLY"
    assert output["maturity_records"] == 4
    assert output["unique_maturity_rows_matched"] == 2
    assert output["unmatched_maturity_rows"] == 2
    assert output["matched_contract_source_counts"] == {"BORROWING": 1, "CAPTACIONES": 1}
    assert output["unique_matches_with_original_currency_code"] == 2
    assert output["cashflows_recognized"] == 0
    assert output["payment_schedule_certified"] is False
    assert "P1" not in str(output)
    assert "A1" not in str(output)
    assert "200" not in str(output)


def test_duplicate_in_contract_index_blocks_unique_join():
    output = audit_obligation_maturity_identity(reader=Reader(duplicate=True), cutoff=CUTOFF)
    assert output["status"] == "AMBIGUOUS_LINKAGE_REVIEW"
    assert output["ambiguous_maturity_rows"] == 1
    assert output["unique_maturity_rows_matched"] == 1
    assert output["contract_sources"][0]["duplicate_identity_rows"] == 1


def test_missing_issuer_never_falls_back_to_operation_id_only():
    output = audit_obligation_maturity_identity(reader=Reader(omit_key=True), cutoff=CUTOFF)
    assert output["maturity_rows_without_composite_identity"] == 1
    assert output["unique_maturity_rows_matched"] == 1


def test_source_header_mismatch_prevents_approval():
    output = audit_obligation_maturity_identity(reader=Reader(wrong_header=True), cutoff=CUTOFF)
    assert output["status"] == "BLOCKED_SOURCE_HEADER_MISMATCH"
    assert output["contract_sources"][1]["same_entity_and_reporting_period"] is False
    assert output["currency_approved_for_projection"] is False


def test_missing_original_source_not_considered_empty():
    output = audit_obligation_maturity_identity(reader=Reader(no_deposits=True), cutoff=CUTOFF)
    assert output["status"] == "PARTIAL_SOURCE_COVERAGE"
    assert output["unique_maturity_rows_matched"] == 1
    assert output["contract_sources"][0]["status"] == "SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO"
