from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from aip.product.configured.irrbb.captaciones_maturity_19band_audit import (
    EVIDENCE_ONLY,
    inspect_fixed_term_maturities,
)


class _Reader:
    def __init__(self, rows, *, period=date(2026, 9, 1)) -> None:
        self.rows = rows
        self.period = period

    def resolve_source(self, *, key, cutoff_date):
        assert key == "CAPTACIONES"
        assert cutoff_date == date(2026, 9, 30)
        return SimpleNamespace(
            path=Path("Pasivos_Cuentas_Contables_210.xml"),
            header=SimpleNamespace(periodo=self.period),
        )

    def iter_records(self, source):
        for index, row in enumerate(self.rows, start=1):
            yield SimpleNamespace(record_id=str(index), values=row)


def _row(
    *,
    account="21301",
    currency="1",
    balance="10.25",
    rate="F",
    maturity="15/10/2026",
):
    return {
        "CuentaContablePrincipal": account,
        "TipoMonedaObligacion": currency,
        "SaldoPrincipal": balance,
        "TipoTasa": rate,
        "FechaVencimiento": maturity,
    }


def test_audit_bands_only_observed_fixed_term_and_keeps_nmd_separate():
    rows = [
        _row(balance="100.15"),
        _row(balance="20.02", currency="2", maturity="30/10/2026"),
        _row(account="21103", balance="90", maturity=""),
        _row(account="21104", balance="30"),
        _row(rate="V", balance="40"),
        _row(maturity="", balance="50"),
        _row(maturity="mal", balance="60"),
        _row(maturity="01/01/2025", balance="70"),
        _row(account="99999", balance="80"),
        _row(balance="-1"),
        _row(currency="", balance="120"),
    ]
    result = inspect_fixed_term_maturities(_Reader(rows), date(2026, 9, 30))
    assert result["status"] == EVIDENCE_ONLY
    assert result["source_records"] == 11
    assert result["observed_records"] == 2
    assert result["excluded_records"] == 9
    assert len(result["bands"]) == 2
    assert {(x["currency_code"], x["ordinal"], x["source_principal"]) for x in result["bands"]} == {
        ("1", 2, "100.15"),
        ("2", 2, "20.02"),
    }
    excluded = {row["reason"]: row["records"] for row in result["excluded"]}
    assert excluded == {
        "SIGHT_NMD_BEHAVIORAL_PROFILE_REQUIRED": 1,
        "MATURED_TERM_POLICY_REQUIRED": 1,
        "TERM_NOT_FIXED_REPRICING_REQUIRED": 1,
        "TERM_MISSING_MATURITY": 1,
        "TERM_INVALID_MATURITY": 1,
        "TERM_PAST_MATURITY": 1,
        "UNSUPPORTED_ACCOUNT": 1,
        "INVALID_PRINCIPAL": 1,
        "MISSING_CURRENCY": 1,
    }
    assert "operation_id" not in str(result).lower()


def test_nmd_is_never_bucketed_even_when_xml_contains_maturity():
    result = inspect_fixed_term_maturities(
        _Reader([_row(account="21204", maturity="30/12/2026")]),
        date(2026, 9, 30),
    )
    assert result["bands"] == []
    assert result["excluded"][0]["reason"] == "SIGHT_NMD_BEHAVIORAL_PROFILE_REQUIRED"


def test_source_month_must_match_cutoff():
    with pytest.raises(ValueError, match="reporting month"):
        inspect_fixed_term_maturities(
            _Reader([_row()], period=date(2026, 8, 1)),
            date(2026, 9, 30),
        )
