"""Deterministic fixtures validate booking gates; never used as live forecasts."""

from datetime import date
from decimal import Decimal

import pytest

from aip.product.configured.liquidity.sugef210_master_maturity_bridge import (
    build_master_principal_evidence,
)

CUTOFF = date(2026, 9, 30)
SHA = "a" * 64


def _row(
    line: int,
    *,
    currency: str = "DOLAR",
    principal: str = "125.50",
    maturity: date | None = date(2026, 10, 31),
) -> dict:
    return {
        "source_row": line,
        "source_currency": currency,
        "currency": currency,
        "principal_balance": float(principal) if principal else None,
        "maturity_date": maturity,
        "source_values": {
            "Saldo Principal": principal,
            "Fecha Vencimiento": maturity.isoformat() if maturity else "",
        },
    }


def test_exact_native_source_cell_preserves_dolar_usd_and_maturity():
    evidence = build_master_principal_evidence(
        cutoff=CUTOFF,
        master_sha256=SHA,
        positions=(_row(4), _row(5, currency="COLONES", principal="80.25")),
        principal_source_header="Saldo Principal",
        maturity_source_header="Fecha Vencimiento",
    )
    assert evidence.positions_read == 2
    assert len(evidence.flows) == 2
    assert evidence.flows[0].currency == "USD"
    assert evidence.flows[0].amount == Decimal("125.50")
    assert evidence.flows[1].currency == "CRC"
    assert evidence.principal_by_currency == (
        ("CRC", Decimal("80.25")),
        ("USD", Decimal("125.50")),
    )
    assert not evidence.complete_investment_cashflow_coverage


def test_no_inferred_maturity_currency_or_principal_and_no_past_rollover():
    excluded = (
        _row(1, currency="UNKNOWN"),
        _row(2, principal=""),
        _row(3, maturity=None),
        _row(4, maturity=CUTOFF),
    )
    evidence = build_master_principal_evidence(
        cutoff=CUTOFF,
        master_sha256=SHA,
        positions=excluded,
        principal_source_header="Saldo Principal",
        maturity_source_header="Fecha Vencimiento",
    )
    assert not evidence.flows
    assert [entry.reason for entry in evidence.excluded] == [
        "CURRENCY_NOT_CERTIFIED",
        "PRINCIPAL_ORIGINAL_CELL_UNVERIFIED",
        "MATURITY_ORIGINAL_CELL_UNVERIFIED",
        "MATURED_OR_NON_FUTURE_POSITION",
    ]


def test_duplicate_source_row_or_missing_source_hash_blocked():
    with pytest.raises(ValueError, match="Duplicate investment"):
        build_master_principal_evidence(
            cutoff=CUTOFF,
            master_sha256=SHA,
            positions=(_row(1), _row(1)),
            principal_source_header="Saldo Principal",
            maturity_source_header="Fecha Vencimiento",
        )
    with pytest.raises(ValueError, match="SHA-256"):
        build_master_principal_evidence(
            cutoff=CUTOFF,
            master_sha256="UNKNOWN",
            positions=(_row(1),),
            principal_source_header="Saldo Principal",
            maturity_source_header="Fecha Vencimiento",
        )


def test_missing_native_header_blocks_numeric_normalization_fallback():
    evidence = build_master_principal_evidence(
        cutoff=CUTOFF,
        master_sha256=SHA,
        positions=(_row(1),),
        principal_source_header=None,
        maturity_source_header="Fecha Vencimiento",
    )
    assert len(evidence.flows) == 0
    assert evidence.excluded[0].reason == "PRINCIPAL_ORIGINAL_CELL_UNVERIFIED"


def test_original_master_reader_normalized_keys_are_respected():
    row = _row(11, currency="DOLAR", principal="430.55")
    row["source_values"] = {
        "saldo principal": "430.55",
        "fecha vencimiento": "2026-10-31",
    }
    result = build_master_principal_evidence(
        cutoff=CUTOFF, master_sha256=SHA, positions=(row,),
        principal_source_header="Saldo Principal",
        maturity_source_header="Fecha Vencimiento",
    )
    assert len(result.flows) == 1
    assert result.flows[0].amount == Decimal("430.55")
    assert result.flows[0].currency == "USD"
    assert not result.excluded


def test_header_accents_do_not_discard_original_contractual_cells():
    row = _row(12, currency="COLONES", principal="91.25")
    row["source_values"] = {
        "saldo principal": "91.25",
        "fecha vencimiento": "2026-10-31",
    }
    result = build_master_principal_evidence(
        cutoff=CUTOFF, master_sha256=SHA, positions=(row,),
        principal_source_header="SÁLDO PRÍNCIPAL",
        maturity_source_header="Fécha Véncimiento",
    )
    assert len(result.flows) == 1
    assert result.flows[0].currency == "CRC"
