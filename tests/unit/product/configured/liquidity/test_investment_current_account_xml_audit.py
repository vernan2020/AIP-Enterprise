from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaHeader,
    XMLConfiaRecord,
    XMLConfiaResolvedSource,
)
from aip.product.configured.liquidity.investment_current_account_xml_audit import (
    InvestmentCurrentAccountPolicy,
    audit_investment_current_accounts,
)


CUTOFF = date(2026, 9, 30)


class _Reader:
    def __init__(self, rows: tuple[XMLConfiaRecord, ...], path: Path):
        self.rows = rows
        self.path = path

    def resolve_source(self, *, key: str, cutoff_date: date) -> XMLConfiaResolvedSource:
        assert key == "INVESTMENT"
        assert cutoff_date == CUTOFF
        return XMLConfiaResolvedSource(
            key=key, path=self.path,
            header=XMLConfiaHeader(
                clase_dato="INV", archivo="INVESTMENT", periodo=date(2026, 9, 1),
                id_entidad="3004045138", tipo_carga="1", tipo_moneda="1"
            ),
        )

    def iter_records(self, source: XMLConfiaResolvedSource):
        assert source.path == self.path
        yield from self.rows

    @staticmethod
    def sha256(path: Path) -> str:
        return "TEST-SHA256"


def _record(identity: str, account: str, currency: str, principal: str, isin: str = ""):
    return XMLConfiaRecord(
        record_id=identity, action="1",
        values={
            "CuentaContablePrincipal": account,
            "TipoMonedaValorFacial": currency,
            "SaldoPrincipal": principal,
            "CodISIN": isin,
        },
    )


def test_xml_account_inventory_does_not_assume_demand_or_count_matched_master(tmp_path):
    r = _Reader(
        (
            _record("1", "C100", "1", "100.15", "ISIN1"),
            _record("2", "C100", "1", "200", ""),
            _record("3", "C200", "2", "300.45", "ISIN2"),
        ),
        tmp_path / "Crediticio_InversionesActivas.xml",
    )
    result = audit_investment_current_accounts(
        reader=r, cutoff=CUTOFF,
        policy=InvestmentCurrentAccountPolicy(
            approved_account_codes=frozenset({"C100"}),
            approval_reference="ALCO-2026-09-ACCOUNT-CLASSIFICATION",
        ),
        master_isins=frozenset({"ISIN1"}),
    )
    assert result.status == "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH"
    assert result.cash_available_today is None
    assert result.records_read == 3
    accounts = {(x.account_code, x.currency_source_code): x for x in result.groups}
    assert accounts[("C100", "1")].principal == 300.15
    assert accounts[("C100", "1")].master_identifier_matches == 1
    assert accounts[("C100", "1")].unverified_master_overlap == 1
    assert accounts[("C100", "1")].classification == "APPROVED_CURRENT_ACCOUNT_CANDIDATE"
    assert accounts[("C200", "2")].classification == "NOT_APPROVED_FOR_CURRENT_ACCOUNT"
    assert accounts[("C200", "2")].unverified_master_overlap == 1


def test_xml_accounts_require_approved_code_and_do_not_infer_cash(tmp_path):
    reader = _Reader((_record("1", "102030", "1", "1000"),), tmp_path / "inv.xml")
    result = audit_investment_current_accounts(
        reader=reader, cutoff=CUTOFF,
        policy=InvestmentCurrentAccountPolicy(
            approved_account_codes=frozenset(), approval_reference=""
        ),
    )
    assert result.groups[0].classification == "NOT_APPROVED_FOR_CURRENT_ACCOUNT"
    assert result.cash_available_today is None
    with pytest.raises(ValueError, match="approval"):
        InvestmentCurrentAccountPolicy(
            approved_account_codes=frozenset({"102030"}), approval_reference=""
        )


def test_xml_invalid_principal_is_audited_without_creating_liquidity(tmp_path):
    r = _Reader(
        (_record("1", "", "1", "not-a-number"), _record("2", "100", "1", "-100")),
        tmp_path / "inv.xml",
    )
    result = audit_investment_current_accounts(
        reader=r, cutoff=CUTOFF,
        policy=InvestmentCurrentAccountPolicy(frozenset(), ""),
    )
    assert result.invalid_source_principal == 2
    assert result.missing_account_codes == 1
    assert result.cash_available_today is None
