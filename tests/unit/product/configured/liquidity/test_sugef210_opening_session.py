"""Governed SUGEF210 opening ingestion: synthetic unit fixtures only."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from aip.product.configured.liquidity.investment_current_account_xml_audit import (
    InvestmentXMLCurrentAccountAudit,
    InvestmentXMLRecordEvidence,
)
from aip.product.configured.liquidity.sugef210_opening_session import (
    run_configured_sight_opening,
)

CUTOFF = date(2026, 9, 30)


def _sample_audit() -> InvestmentXMLCurrentAccountAudit:
    return InvestmentXMLCurrentAccountAudit(
        cutoff=CUTOFF,
        xml_month=date(2026, 9, 1),
        xml_sha256="a" * 64,
        xml_filename="Crediticio_InversionesActivas.xml",
        entity_id="TEST-INSTITUTION",
        records_read=1,
        groups=(),
        invalid_source_principal=0,
        missing_account_codes=0,
        records=(
            InvestmentXMLRecordEvidence(
                source_reference="TEST:2026-09-01:INVESTMENT:ROW-00000001",
                raw_record_id="1",
                record_ordinal=1,
                action="1",
                account_code="9990",
                currency_source_code="2",
                raw_principal="200.00",
                principal=Decimal("200.00"),
                instrument_id="TEST-001",
                instrument_classification_original="5",
                maturity_original="",
                isin="",
                series="",
                classification="APPROVED_CURRENT_ACCOUNT_CANDIDATE",
                master_reconciliation="UNMATCHED_ID_NOT_PROOF_OF_NEW_BALANCE",
            ),
        ),
    )


def _files(tmp_path: Path) -> tuple[Path, Path]:
    original = tmp_path / "institutional-bank-icl-source.xlsx"
    original.write_bytes(b"test-only-source-document")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    approval = tmp_path / "sight-approval.json"
    bank = tmp_path / "bank-opening.json"
    approval.write_text(
        json.dumps(
            {
                "schema": "SUGEF210_SIGHT_OPENING_V1",
                "cutoff": CUTOFF.isoformat(),
                "xml_sha256": "a" * 64,
                "account_classification_approval": "TEST-ALCO-AUTHORIZATION",
                "currency_mapping_approval_reference": "TEST-ORIGINAL-CURRENCY-CATALOG",
                "opening_reconciliation_reference": "TEST-TREASURY-ICL-NONDOUBLE",
                "approved_account_codes": ["9990"],
                "approved_currency_mapping": {"2": "USD"},
                "approved_records": [
                    {
                        "source_record_reference": "TEST:2026-09-01:INVESTMENT:ROW-00000001",
                        "accounting_account": "9990",
                        "currency": "USD",
                        "xml_principal": "200.00",
                        "confirmed_available": "75.25",
                        "withdrawal_available_date": CUTOFF.isoformat(),
                        "availability_evidence": "TEST-BANK-VALIDATION",
                        "nonduplication_reconciliation": "TEST-NOT-ALREADY-IN-ICL",
                        "restriction_clearance_reference": "TEST-RESTRICTION-CLEARED",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    bank.write_text(
        json.dumps(
            {
                "schema": "SUGEF210_BANK_OPENING_V1",
                "cutoff": CUTOFF.isoformat(),
                "bank_opening_excluding_sight": {"CRC": "1000", "USD": "10"},
                "opening_certifications": {"CRC": "TEST-BANK-CRC", "USD": "TEST-BANK-USD"},
                "opening_reconciliation_reference": "TEST-TREASURY-ICL-NONDOUBLE",
                "bank_or_icl_source_file": str(original),
                "bank_or_icl_source_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    return approval, bank


def _configure(monkeypatch, tmp_path):
    from aip.product.configured.liquidity import sugef210_opening_session as module

    class Loader:
        @staticmethod
        def load_source_config():
            return SimpleNamespace(
                xml_confia=SimpleNamespace(enabled=True, root=str(tmp_path)),
                folder_watch=SimpleNamespace(
                    enabled=True,
                    portfolio_root=str(tmp_path),
                    portfolio_master_pattern="*.xlsx",
                ),
            )

    class Master:
        @staticmethod
        def read(*_args, **_kwargs):
            return SimpleNamespace(
                source_status="HEALTHY",
                normalized_positions=[{"isin": "TEST-NOT-A-SIGHT-ISIN", "series": "TEST-SERIES"}],
            )

    master_file = tmp_path / "exact-cutoff-master.xlsx"
    master_file.write_bytes(b"test-only-master")
    monkeypatch.setattr(module, "EnvironmentLoader", Loader)
    monkeypatch.setattr(
        module,
        "resolve_exact_cutoff_master",
        lambda *_args: ("EXACT", master_file, 1),
    )
    monkeypatch.setattr(module, "InstitutionalPortfolioMasterReader", Master)
    monkeypatch.setattr(module, "XMLConfiaMonthlySourceReader", lambda _root: object())
    monkeypatch.setattr(
        module, "audit_investment_current_accounts", lambda **_kwargs: _sample_audit()
    )


def test_real_source_session_wires_verified_xml_sight_to_partial_365_day_engine(
    monkeypatch, tmp_path
):
    _configure(monkeypatch, tmp_path)
    approval, bank = _files(tmp_path)
    result = run_configured_sight_opening(
        cutoff=CUTOFF,
        scenario="BASE",
        approval_manifest=approval,
        bank_support_manifest=bank,
    )
    assert result.sight_records_approved == 1
    assert result.assembly.projection.source_flow_count == 0
    assert result.assembly.projection.rows[0].projected_liquidity == Decimal("1000")
    assert result.assembly.projection.rows[17].projected_liquidity == Decimal("85.25")
    assert len(result.assembly.projection.rows) == 34
    assert not result.assembly.projection.certified_comprehensive
    assert result.sight_source_sha256 == "a" * 64


def test_corrupt_bank_evidence_blocks_original_xml_from_opening(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    approval, bank = _files(tmp_path)
    content = json.loads(bank.read_text())
    content["bank_or_icl_source_sha256"] = "0" * 64
    bank.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="hash"):
        run_configured_sight_opening(
            cutoff=CUTOFF,
            scenario="BASE",
            approval_manifest=approval,
            bank_support_manifest=bank,
        )


def test_bank_approval_must_be_separate_and_matching(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    approval, bank = _files(tmp_path)
    with pytest.raises(ValueError, match="separate"):
        run_configured_sight_opening(
            cutoff=CUTOFF,
            scenario="BASE",
            approval_manifest=approval,
            bank_support_manifest=approval,
        )
    content = json.loads(bank.read_text())
    content["opening_reconciliation_reference"] = "ANOTHER-RECONCILIATION"
    bank.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="nonduplication"):
        run_configured_sight_opening(
            cutoff=CUTOFF,
            scenario="BASE",
            approval_manifest=approval,
            bank_support_manifest=bank,
        )


def test_missing_master_prevents_on_demand_balance_acceptance(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    approval, bank = _files(tmp_path)
    from aip.product.configured.liquidity import sugef210_opening_session as module

    monkeypatch.setattr(module, "resolve_exact_cutoff_master", lambda *_args: ("MISSING", None, 0))
    with pytest.raises(ValueError, match="Master unavailable"):
        run_configured_sight_opening(
            cutoff=CUTOFF,
            scenario="BASE",
            approval_manifest=approval,
            bank_support_manifest=bank,
        )


def test_cutoff_and_source_currency_attestation_fail_closed(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    approval, bank = _files(tmp_path)
    with pytest.raises(ValueError, match="cutoff"):
        run_configured_sight_opening(
            cutoff=date(2026, 10, 31),
            scenario="BASE",
            approval_manifest=approval,
            bank_support_manifest=bank,
        )
    content = json.loads(bank.read_text())
    content["opening_certifications"] = {"CRC": "TEST-CERT"}
    bank.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="Both CRC and USD"):
        run_configured_sight_opening(
            cutoff=CUTOFF,
            scenario="BASE",
            approval_manifest=approval,
            bank_support_manifest=bank,
        )


def test_bank_icl_document_cannot_be_the_investment_master(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    approval, bank = _files(tmp_path)
    original_master = tmp_path / "exact-cutoff-master.xlsx"
    content = json.loads(bank.read_text(encoding="utf-8"))
    content["bank_or_icl_source_file"] = str(original_master)
    content["bank_or_icl_source_sha256"] = hashlib.sha256(original_master.read_bytes()).hexdigest()
    bank.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(ValueError, match="independent of approvals and Master"):
        run_configured_sight_opening(
            cutoff=CUTOFF,
            scenario="BASE",
            approval_manifest=approval,
            bank_support_manifest=bank,
        )


def test_approved_original_master_principal_generates_real_dated_inflow(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    from aip.product.configured.liquidity import sugef210_opening_session as module

    approval, bank = _files(tmp_path)
    source = tmp_path / "exact-cutoff-master.xlsx"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    maturity = CUTOFF + timedelta(days=31)

    class RealMasterRecord:
        @staticmethod
        def read(*_args, **_kwargs):
            return SimpleNamespace(
                source_status="HEALTHY",
                detected_column_mapping={
                    "principal_balance": "Saldo Principal",
                    "maturity_date": "Fecha Vencimiento",
                },
                normalized_positions=[
                    {
                        "isin": "UNRELATED-TEST-ISIN",
                        "series": "UNRELATED-TEST-SERIES",
                        "source_currency": "CRC",
                        "source_row": "ROW-3",
                        "maturity_date": maturity,
                        "source_values": {
                            "saldo principal": "120",
                            "fecha vencimiento": maturity.isoformat(),
                        },
                    }
                ],
            )

    monkeypatch.setattr(module, "InstitutionalPortfolioMasterReader", RealMasterRecord)
    doc = json.loads(approval.read_text(encoding="utf-8"))
    doc["master_principal_authorization"] = {
        "master_sha256": digest,
        "approval_reference": "TEST-TREASURY-PRINCIPAL",
        "approved_principal_records": [
            {
                "cashflow_reference": f"MASTER:{digest}:ROW-3:PRINCIPAL",
                "payment_date": maturity.isoformat(),
                "original_principal": "120",
                "currency": "CRC",
                "settlement_availability_reference": "TEST-BANK-CUSTODIAN",
                "restriction_clearance_reference": "TEST-UNENCUMBERED",
                "nonduplication_reference": "TEST-INVESTMENT-NONDUP",
            }
        ],
    }
    approval.write_text(json.dumps(doc), encoding="utf-8")
    result = run_configured_sight_opening(
        cutoff=CUTOFF,
        scenario="BASE",
        approval_manifest=approval,
        bank_support_manifest=bank,
    )
    assert result.master_principal_events_approved == 1
    assert result.assembly.projection.source_flow_count == 1
    assert result.assembly.projection.rows[12].asset_inflows == Decimal("120")
    assert result.assembly.projection.rows[12].projected_liquidity == Decimal("1120")
    assert result.assembly.projection.rows[17 + 12].projected_liquidity == Decimal("85.25")
    assert not result.assembly.projection.certified_comprehensive
    assert "INVESTMENT_COUPONS_AND_UNRESOLVED_MATURITIES" in (
        result.assembly.missing_institutional_evidence
    )


def test_master_principal_without_original_source_hash_is_blocked(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    approval, bank = _files(tmp_path)
    document = json.loads(approval.read_text(encoding="utf-8"))
    document["master_principal_authorization"] = {
        "master_sha256": "0" * 64,
        "approval_reference": "TEST-TREASURY-PRINCIPAL",
        "approved_principal_records": [{"cashflow_reference": "NONEXISTENT"}],
    }
    approval.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="no longer matches actual Master"):
        run_configured_sight_opening(
            cutoff=CUTOFF,
            scenario="BASE",
            approval_manifest=approval,
            bank_support_manifest=bank,
        )


def test_real_session_loads_approved_external_contract_ledger_and_native_credit_cash(
    monkeypatch, tmp_path
):
    _configure(monkeypatch, tmp_path)
    from aip.product.configured.liquidity import sugef210_opening_session as module

    approval, bank = _files(tmp_path)
    xml = tmp_path / "CREDIT.xml"
    xml.write_bytes(b"TEST-SOURCE-CREDIT-XML")
    xml_hash = hashlib.sha256(xml.read_bytes()).hexdigest()
    ledger = tmp_path / "institutional-credit-ledger.csv"
    fields = (
        "source_key",
        "source_ordinal",
        "source_record_id",
        "account_code",
        "original_currency_code",
        "currency",
        "original_principal",
        "maturity_date",
        "payment_reference",
        "payment_date",
        "flow_type",
        "amount",
        "availability_reference",
    )
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "source_key": "CREDIT",
                "source_ordinal": "1",
                "source_record_id": "CREDIT-1",
                "account_code": "131",
                "original_currency_code": "1",
                "currency": "CRC",
                "original_principal": "120",
                "maturity_date": "2027-09-30",
                "payment_reference": "P1",
                "payment_date": "2026-10-31",
                "flow_type": "PRINCIPAL",
                "amount": "120",
                "availability_reference": "TEST-LEDGER-BANK-SETTLEMENT",
            }
        )
    ledger_hash = hashlib.sha256(ledger.read_bytes()).hexdigest()

    class Reader:
        def __init__(self, _root):
            pass

        @staticmethod
        def resolve_source(*, key, cutoff_date):
            assert key == "CREDIT" and cutoff_date == CUTOFF
            return SimpleNamespace(
                path=xml,
                header=SimpleNamespace(periodo=date(2026, 9, 1), id_entidad="TEST"),
            )

        @staticmethod
        def iter_records(_source):
            yield SimpleNamespace(
                record_id="CREDIT-1",
                values={
                    "SaldoPrincipalOperacionCrediticia": "120",
                    "TipoMonedaOperacion": "1",
                    "CuentaContablePrincipal": "131",
                    "FechaVencimiento": "30/09/2027",
                },
            )

        @staticmethod
        def sha256(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()

    monkeypatch.setattr(module, "XMLConfiaMonthlySourceReader", Reader)
    document = json.loads(approval.read_text(encoding="utf-8"))
    document["xml_contractual_schedule"] = {
        "ledger_file": str(ledger),
        "ledger_sha256": ledger_hash,
        "approved_xml_sha256": {"CREDIT": xml_hash},
        "approved_currency_codes": {"1": "CRC"},
        "approved_term_deposit_codes": [],
        "source_payment_approval": "TEST-TREASURY-CREDIT-LEDGER",
        "settlement_approval": "TEST-BANK-CREDIT-CASH-CALENDAR",
        "nonduplication_reference": "TEST-CREDIT-NOT-MASTER",
    }
    approval.write_text(json.dumps(document), encoding="utf-8")
    result = run_configured_sight_opening(
        cutoff=CUTOFF,
        scenario="BASE",
        approval_manifest=approval,
        bank_support_manifest=bank,
    )
    assert result.xml_contractual_events_approved == 1
    assert result.master_principal_events_approved == 0
    assert result.assembly.projection.source_flow_count == 1
    assert result.assembly.projection.rows[12].net_flow == Decimal("120")
    assert result.assembly.projection.rows[12].projected_liquidity == Decimal("1120")
    assert result.assembly.projection.rows[17 + 12].net_flow == 0
    assert not result.assembly.projection.certified_comprehensive
