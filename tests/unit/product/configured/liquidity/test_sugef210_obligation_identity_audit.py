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
                "SaldoPrincipal": "200",
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
                    "SaldoPrincipal": "300",
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


class ReconciledReader(Reader):
    """One valid split, one unreconciled principal, and an unbanded contract."""

    def iter_records(self, source):
        if source.key == "CAPTACIONES":
            for index, principal in (("A1", "200"), ("A9", "50")):
                yield XMLConfiaRecord(
                    index,
                    "insertar",
                    {
                        "IdAcreedor": "P1",
                        "IdOperacion": index,
                        "TipoMonedaObligacion": "1",
                        "CuentaContablePrincipal": "211",
                        "SaldoPrincipal": principal,
                        "TipoCuenta": "VISTA" if index == "A9" else "TERM",
                        "FechaVencimiento": "" if index == "A9" else "30/12/2026",
                    },
                )
        elif source.key == "BORROWING":
            yield from super().iter_records(source)
        elif source.key == "BORROWING_MATURITY":
            for index, (issuer, operation, principal, band) in enumerate(
                (
                    ("P1", "A1", "100", "01"),
                    ("P1", "A1", "100", "02"),
                    ("P2", "A2", "250", "03"),
                )
            ):
                yield XMLConfiaRecord(
                    str(index),
                    "insertar",
                    {
                        "IdAcreedor": issuer,
                        "IdOperacion": operation,
                        "SaldoaPagarPrincipal": principal,
                        "TipoRangoPasivo": band,
                    },
                )


def test_distinct_contracts_and_native_principal_reconciliation():
    output = audit_obligation_maturity_identity(reader=ReconciledReader(), cutoff=CUTOFF)
    assert output["unique_maturity_rows_matched"] == 3
    assert output["distinct_contracts_with_maturity_bands"] == 2
    assert output["matched_maturity_rows_on_repeated_contracts"] == 1
    assert output["contract_identities_without_maturity_bands_by_source"] == {"CAPTACIONES": 1}
    assert output["range_code_record_counts"] == {"01": 1, "02": 1, "03": 1}
    assert output["unbanded_contracts_by_original_type_code"] == {"CAPTACIONES:VISTA": 1}
    assert output["unbanded_contracts_by_original_maturity_state"] == {"SOURCE_MATURITY_BLANK": 1}
    assert output["unbanded_contracts_by_native_currency_code"] == {"1": 1}
    totals = output["principal_reconciliation"]
    assert totals["distinct_contracts_reconciled_exactly"] == 1
    assert totals["distinct_contracts_with_principal_difference"] == 1
    assert totals["matched_contracts_without_usable_band_principal"] == 0
    assert totals["monetary_tolerance_applied"] is False
    assert output["cashflows_recognized"] == 0
    assert "250" not in str(output)
    assert "P1" not in str(output)


class InvalidBandReader(ReconciledReader):
    def iter_records(self, source):
        if source.key == "BORROWING_MATURITY":
            yield XMLConfiaRecord(
                "1",
                "insertar",
                {
                    "IdAcreedor": "P1",
                    "IdOperacion": "A1",
                    "SaldoaPagarPrincipal": "NaN",
                    "TipoRangoPasivo": "SENSITIVE BAD STRING",
                },
            )
        else:
            yield from super().iter_records(source)


def test_non_finite_principal_and_unexpected_range_code_are_not_accepted():
    output = audit_obligation_maturity_identity(reader=InvalidBandReader(), cutoff=CUTOFF)
    assert output["maturity_principal_values_missing_or_invalid"] == 1
    assert (
        output["principal_reconciliation"]["matched_contracts_without_usable_band_principal"] == 1
    )
    assert output["range_code_record_counts"] == {"(SIN CÓDIGO)": 1}
    assert "SENSITIVE" not in str(output)
    assert output["cashflows_recognized"] == 0


class BothInvalidPrincipalReader(ReconciledReader):
    def iter_records(self, source):
        if source.key == "CAPTACIONES":
            yield XMLConfiaRecord(
                "one",
                "insertar",
                {
                    "IdAcreedor": "P1",
                    "IdOperacion": "A1",
                    "SaldoPrincipal": "",
                    "TipoMonedaObligacion": "1",
                    "CuentaContablePrincipal": "211",
                    "TipoCuenta": "TERM",
                },
            )
        elif source.key == "BORROWING_MATURITY":
            yield XMLConfiaRecord(
                "one",
                "insertar",
                {
                    "IdAcreedor": "P1",
                    "IdOperacion": "A1",
                    "SaldoaPagarPrincipal": "",
                    "TipoRangoPasivo": "2",
                },
            )
        else:
            yield from super().iter_records(source)


def test_invalid_source_and_band_balances_are_counted_independently():
    output = audit_obligation_maturity_identity(reader=BothInvalidPrincipalReader(), cutoff=CUTOFF)
    principal = output["principal_reconciliation"]
    assert principal["matched_contracts_without_usable_source_principal"] == 1
    assert principal["matched_contracts_without_usable_band_principal"] == 1
    assert principal["distinct_contracts_with_invalid_principal_on_either_side"] == 1
    assert principal["source_principal_issue_causes"] == {"BLANK": 1}
    assert output["maturity_principal_values_missing_or_invalid"] == 1
    assert output["cashflows_recognized"] == 0


class SignedNegativeReader(ReconciledReader):
    def __init__(self, *, band_principal="-12", original_principal="-12"):
        super().__init__()
        self.band_principal = band_principal
        self.original_principal = original_principal

    def iter_records(self, source):
        if source.key == "CAPTACIONES":
            yield XMLConfiaRecord(
                "one",
                "insertar",
                {
                    "IdAcreedor": "P1",
                    "IdOperacion": "A1",
                    "SaldoPrincipal": self.original_principal,
                    "TipoMonedaObligacion": "1",
                    "CuentaContablePrincipal": "211",
                    "TipoCuenta": "4",
                    "FechaVencimiento": "10/10/2026",
                },
            )
        elif source.key == "BORROWING_MATURITY":
            yield XMLConfiaRecord(
                "one",
                "insertar",
                {
                    "IdAcreedor": "P1",
                    "IdOperacion": "A1",
                    "SaldoaPagarPrincipal": self.band_principal,
                    "TipoRangoPasivo": "2",
                },
            )
        else:
            yield from super().iter_records(source)


def test_negative_principal_matches_signed_source_but_never_becomes_cash():
    result = audit_obligation_maturity_identity(reader=SignedNegativeReader(), cutoff=CUTOFF)
    proof = result["principal_reconciliation"]
    assert proof["negative_contracts_matching_signed_band_total"] == 1
    assert proof["negative_contracts_differing_signed_band_total"] == 0
    assert proof["negative_banded_contracts"] == 1
    assert proof["distinct_contracts_reconciled_exactly"] == 0
    assert proof["signed_negative_balances_accepted_as_cashflows"] is False
    assert result["cashflows_recognized"] == 0
    assert "-12" not in str(result)


def test_signed_negative_disagreement_and_unusable_band_remain_exceptions():
    different = audit_obligation_maturity_identity(
        reader=SignedNegativeReader(band_principal="-11"), cutoff=CUTOFF
    )
    assert (
        different["principal_reconciliation"]["negative_contracts_differing_signed_band_total"] == 1
    )
    missing = audit_obligation_maturity_identity(
        reader=SignedNegativeReader(band_principal=""), cutoff=CUTOFF
    )
    assert (
        missing["principal_reconciliation"]["negative_contracts_without_usable_signed_comparison"]
        == 1
    )
    assert missing["cashflows_recognized"] == 0


def test_unbanded_original_type_and_maturity_cross_tab_has_no_amounts():
    result = audit_obligation_maturity_identity(reader=ReconciledReader(), cutoff=CUTOFF)
    assert result["unbanded_contracts_by_type_and_maturity_state"] == {
        "CAPTACIONES:VISTA:SOURCE_MATURITY_BLANK": 1
    }
    assert "P1" not in str(result)
    assert result["cashflows_recognized"] == 0


class FutureUnbandedReader(ReconciledReader):
    """Synthetic source dates demonstrate band grouping without payable events."""

    def iter_records(self, source):
        yield from super().iter_records(source)
        if source.key == "CAPTACIONES":
            for operation, account_type, currency, maturity in (
                ("A10", "4", "2", "01/10/2026"),
                ("A11", "2", "1", "30/12/2026"),
                ("A12", "4", "1", "01/10/2027"),
                ("A13", "2", "1", "30/09/2026"),
            ):
                yield XMLConfiaRecord(
                    operation,
                    "insertar",
                    {
                        "IdAcreedor": "P1",
                        "IdOperacion": operation,
                        "SaldoPrincipal": "10",
                        "TipoMonedaObligacion": currency,
                        "CuentaContablePrincipal": "211",
                        "TipoCuenta": account_type,
                        "FechaVencimiento": maturity,
                    },
                )


def test_evidenced_unbanded_dates_are_grouped_in_17_horizons_without_cashflows():
    result = audit_obligation_maturity_identity(reader=FutureUnbandedReader(), cutoff=CUTOFF)
    preview = result["unbanded_date_evidence_by_sugef210_window"]
    assert preview["status"] == "DATE_REFERENCE_ONLY_NOT_PAYMENT_SCHEDULE"
    assert preview["regulatory_bands"] == 17
    assert preview["future_within_365d_count"] == 2
    assert preview["by_window"] == {"D01": 1, "Q01": 1}
    assert preview["by_source_type_native_currency_window"] == {
        "CAPTACIONES:2:1:Q01": 1,
        "CAPTACIONES:4:2:D01": 1,
    }
    assert preview["payments_recognized"] == 0
    assert result["cashflows_recognized"] == 0
    assert result["payment_schedule_certified"] is False


def test_single_principal_difference_is_attributed_only_to_original_source_codes():
    result = audit_obligation_maturity_identity(reader=ReconciledReader(), cutoff=CUTOFF)
    differences = result["principal_reconciliation"]
    assert differences["distinct_contracts_with_principal_difference"] == 1
    assert differences["differences_by_source_type_native_currency"] == {
        "BORROWING:(SIN CÓDIGO):2": 1
    }
    assert "P2" not in str(result)
    assert "250" not in str(result)


class ClusteredNextDayReader(ReconciledReader):
    """Synthetic repeated next-day dates, never a payment schedule."""

    def __init__(self, *, next_day_count=110):
        super().__init__()
        self.next_day_count = next_day_count

    def iter_records(self, source):
        yield from super().iter_records(source)
        if source.key == "CAPTACIONES":
            for index in range(self.next_day_count):
                yield XMLConfiaRecord(
                    str(index + 100),
                    "insertar",
                    {
                        "IdAcreedor": "P1",
                        "IdOperacion": f"Q{index}",
                        "SaldoPrincipal": "100",
                        "TipoMonedaObligacion": "1" if index % 2 else "2",
                        "CuentaContablePrincipal": "211",
                        "TipoCuenta": "4",
                        "FechaVencimiento": "01/10/2026",
                    },
                )


def test_large_next_day_cluster_flags_date_semantics_without_cash():
    result = audit_obligation_maturity_identity(reader=ClusteredNextDayReader(), cutoff=CUTOFF)
    cluster = result["unbanded_date_evidence_by_sugef210_window"]["next_day_concentration_review"]
    assert cluster["status"] == "REVIEW_SOURCE_DATE_SEMANTICS"
    assert cluster["next_day_after_cutoff"] == "2026-10-01"
    assert cluster["next_day_unbanded_contracts"] == 110
    assert cluster["future_dated_unbanded_contracts"] == 110
    assert cluster["next_day_by_original_source_type_currency"] == {
        "CAPTACIONES:4:1": 55,
        "CAPTACIONES:4:2": 55,
    }
    assert cluster["placeholder_date_confirmed"] is False
    assert cluster["payable_maturity_confirmed"] is False
    assert cluster["cashflow_payments_recognized"] == 0
    assert result["cashflows_recognized"] == 0


def test_small_next_day_cluster_does_not_prove_date_convention():
    result = audit_obligation_maturity_identity(
        reader=ClusteredNextDayReader(next_day_count=2), cutoff=CUTOFF
    )
    cluster = result["unbanded_date_evidence_by_sugef210_window"]["next_day_concentration_review"]
    assert cluster["status"] == "NO_LARGE_NEXT_DAY_CLUSTER_DETECTED"
    assert cluster["next_day_unbanded_contracts"] == 2
    assert cluster["cashflow_payments_recognized"] == 0
