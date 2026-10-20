"""Native CONFIA 210 sight deposits: test fixtures only, no operational DEMO."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from types import SimpleNamespace

import pytest

from aip.product.configured.liquidity.sugef210_demand_deposit_runoff import (
    read_approved_demand_deposit_runoff,
)

CUTOFF = date(2026, 9, 30)


class SourceReader:
    def __init__(self, root: Path):
        self.xml = root / "Pasivos_Cuentas_Contables_210.xml"
        self.xml.write_bytes(b"TEST-ORIGINAL-SOURCE-NOT-REAL-XML")

    def resolve_source(self, *, key, cutoff_date):
        assert key == "CAPTACIONES" and cutoff_date == CUTOFF
        return SimpleNamespace(
            path=self.xml,
            header=SimpleNamespace(periodo=date(2026, 9, 1), id_entidad="TEST-INSTITUTION"),
        )

    def iter_records(self, _source):
        yield SimpleNamespace(
            record_id="TEST-210-SIGHT-1",
            values={
                "CuentaContablePrincipal": "TEST-210",
                "TipoCuenta": "SIGHT",
                "TipoMonedaObligacion": "2",
                "SaldoPrincipal": "100",
            },
        )
        yield SimpleNamespace(
            record_id="TEST-210-TERM-2",
            values={
                "CuentaContablePrincipal": "TEST-210",
                "TipoCuenta": "FIXED-TERM",
                "TipoMonedaObligacion": "2",
                "SaldoPrincipal": "300",
                "FechaVencimiento": "30/09/2027",
            },
        )

    @staticmethod
    def sha256(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy(tmp_path):
    reader = SourceReader(tmp_path)
    path = tmp_path / "approved-runoff.json"
    doc = {
        "schema": "SUGEF210_DEMAND_RUNOFF_V1",
        "cutoff": CUTOFF.isoformat(),
        "scenario": "SYSTEMIC",
        "entity_id": "TEST-INSTITUTION",
        "xml_sha256": reader.sha256(reader.xml),
        "approved_sight_account_codes": ["TEST-210"],
        "approved_sight_type_codes": ["SIGHT"],
        "approved_currency_codes": {"2": "USD"},
        "approved_native_balance_reconciliation": [
            {
                "account_code": "TEST-210",
                "type_code": "SIGHT",
                "currency_source_code": "2",
                "currency": "USD",
                "source_record_count": 1,
                "original_native_balance": "100",
                "reconciliation_reference": "TEST-TREASURY-ACCOUNT-USD",
            }
        ],
        "classification_approval": "TEST-CLASSIFICATION-APPROVAL",
        "currency_mapping_approval": "TEST-NATIVE-CURRENCY-APPROVAL",
        "nonduplication_approval": "TEST-NOT-IN-CONTRACTUAL-SCHEDULE",
        "approved_rules": [
            {
                "reference": "TEST-RUNOFF-D02",
                "exposure_category": "SIGHT:TEST-210:SIGHT:USD",
                "factor": "0.20",
                "projection_day": 2,
                "rationale": "TEST APPROVAL ONLY",
                "approval_reference": "TEST-ALCO-D02",
                "source_reference": "TEST-BEHAVIORAL-MODEL-V1",
                "version": "V1",
                "approved_on": "2026-09-01",
                "valid_from": "2026-09-01",
                "valid_to": "2026-12-31",
                "explicitly_approved": True,
            },
            {
                "reference": "TEST-RUNOFF-W14",
                "exposure_category": "SIGHT:TEST-210:SIGHT:USD",
                "factor": "0.30",
                "projection_day": 14,
                "rationale": "TEST APPROVAL ONLY",
                "approval_reference": "TEST-ALCO-W14",
                "source_reference": "TEST-BEHAVIORAL-MODEL-V1",
                "version": "V1",
                "approved_on": "2026-09-01",
                "valid_from": "2026-09-01",
                "valid_to": "2026-12-31",
                "explicitly_approved": True,
            },
        ],
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return reader, path, doc


def _read(reader, policy, **kwargs):
    return read_approved_demand_deposit_runoff(
        reader=reader,
        cutoff=CUTOFF,
        scenario="SYSTEMIC",
        approval_file=policy,
        **kwargs,
    )


def test_real_xml_selected_demand_amounts_become_governed_outflows_only(tmp_path):
    reader, approval, _ = _policy(tmp_path)
    result = _read(reader, approval)
    assert result.approved_accounts_seen == 1
    assert result.excluded_xml_records == 1
    assert dict(result.source_native_balances)["USD"] == Decimal("100")
    assert result.included_source_ordinals == frozenset({1})
    assert result.reconciled_native_groups == (("TEST-210", "SIGHT", "2", 1, Decimal("100")),)
    assert result.evidence.matched_exposure_count == 1
    assert result.evidence.status == "APPROVED_SCENARIO_EVENTS_ONLY_NOT_FULL_COVERAGE"
    assert len(result.evidence.flows) == 2
    assert [event.payment_date for event in result.evidence.flows] == [
        date(2026, 10, 2),
        date(2026, 10, 14),
    ]
    assert [event.amount for event in result.evidence.flows] == [Decimal("20.00"), Decimal("30.00")]
    assert all(event.currency == "USD" for event in result.evidence.flows)
    assert all(event.area.value == "LIABILITY" for event in result.evidence.flows)
    assert all(event.side.value == "OUTFLOW" for event in result.evidence.flows)
    assert all(event.evidence.value == "GOVERNED_ASSUMPTION" for event in result.evidence.flows)
    assert result.status == "APPROVED_SELECTED_DEMAND_DEPOSITS_NOT_COMPLETE_COVERAGE"


def test_demand_source_hash_currency_and_scenario_are_not_inferred(tmp_path):
    reader, approval, doc = _policy(tmp_path)
    reader.xml.write_bytes(b"NEW-DATA")
    with pytest.raises(ValueError, match="hash changed"):
        _read(reader, approval)
    reader, approval, doc = _policy(tmp_path)
    doc["approved_currency_codes"] = {"1": "CRC"}
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="lacks approved mapping"):
        _read(reader, approval)
    reader, approval, doc = _policy(tmp_path)
    doc["scenario"] = "BASE"
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="another scenario"):
        _read(reader, approval)


def test_term_deposits_and_certified_payment_records_cannot_double_count(tmp_path):
    reader, approval, doc = _policy(tmp_path)
    assert len(_read(reader, approval).evidence.flows) == 2
    with pytest.raises(ValueError, match="scheduled contractual"):
        _read(reader, approval, contractually_scheduled_ordinals=frozenset({1}))
    doc["approved_sight_type_codes"] = ["FIXED-TERM"]
    doc["approved_native_balance_reconciliation"] = [
        {
            "account_code": "TEST-210",
            "type_code": "FIXED-TERM",
            "currency_source_code": "2",
            "currency": "USD",
            "source_record_count": 1,
            "original_native_balance": "300",
            "reconciliation_reference": "TEST-ALCO-RECLASSIFICATION-REQUIRED",
        }
    ]
    doc["approved_rules"] = [
        {**item, "exposure_category": "SIGHT:TEST-210:FIXED-TERM:USD"}
        for item in doc["approved_rules"]
    ]
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="Contractually dated deposit"):
        _read(reader, approval)


def test_cumulative_percentage_cannot_exceed_original_demand_balance(tmp_path):
    reader, approval, doc = _policy(tmp_path)
    doc["approved_rules"][1]["factor"] = "0.90"
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="Cumulative scenario factors"):
        _read(reader, approval)
    doc["approved_rules"][1]["factor"] = "0.30"
    doc["approved_rules"][1]["projection_day"] = 2
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate scenario date"):
        _read(reader, approval)


def test_malformed_balances_missing_catalog_approval_and_missing_row_source(tmp_path):
    reader, approval, doc = _policy(tmp_path)
    doc["approved_sight_account_codes"] = ["NOT-A-REAL-APPROVED-ACCOUNT"]
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="No approved demand-deposit source accounts"):
        _read(reader, approval)
    reader, approval, doc = _policy(tmp_path)
    doc["approved_rules"][0]["explicitly_approved"] = False
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="explicit ALCO"):
        _read(reader, approval)
    reader, approval, doc = _policy(tmp_path)
    doc["xml_sha256"] = ""
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing approved"):
        _read(reader, approval)


def test_native_balance_and_record_count_must_match_independently_approved_group(tmp_path):
    reader, approval, doc = _policy(tmp_path)
    approved = doc["approved_native_balance_reconciliation"][0]
    approved["original_native_balance"] = "101"
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="do not reconcile exactly"):
        _read(reader, approval)
    approved["original_native_balance"] = "100"
    approved["source_record_count"] = 2
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="do not reconcile exactly"):
        _read(reader, approval)
    del doc["approved_native_balance_reconciliation"]
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="native balance reconciliation is mandatory"):
        _read(reader, approval)


def test_xml_account_type_cross_product_cannot_include_unapproved_currency(tmp_path):
    reader, approval, doc = _policy(tmp_path)
    doc["approved_sight_type_codes"] = ["SIGHT", "FIXED-TERM"]
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="lacks independent reconciliation"):
        _read(reader, approval)


def test_sight_rules_must_bind_a_specific_native_currency(tmp_path):
    reader, approval, doc = _policy(tmp_path)
    for rule in doc["approved_rules"]:
        rule["exposure_category"] = "SIGHT:TEST-210:SIGHT"
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="category does not match"):
        _read(reader, approval)


def test_crc_and_usd_same_original_account_support_distinct_authorized_runoff(tmp_path):
    reader, approval, doc = _policy(tmp_path)
    original_iter = reader.iter_records

    def two_currency_rows(source):
        yield from original_iter(source)
        yield SimpleNamespace(
            record_id="TEST-210-SIGHT-CRC-3",
            values={
                "CuentaContablePrincipal": "TEST-210",
                "TipoCuenta": "SIGHT",
                "TipoMonedaObligacion": "1",
                "SaldoPrincipal": "80",
            },
        )

    reader.iter_records = two_currency_rows
    doc["approved_currency_codes"] = {"1": "CRC", "2": "USD"}
    doc["approved_native_balance_reconciliation"].append({
        "account_code": "TEST-210",
        "type_code": "SIGHT",
        "currency_source_code": "1",
        "currency": "CRC",
        "source_record_count": 1,
        "original_native_balance": "80",
        "reconciliation_reference": "TEST-INDEPENDENT-CRC-ACCOUNT-CONTROL",
    })
    doc["approved_rules"].append({
        **doc["approved_rules"][0],
        "reference": "TEST-CRC-D02",
        "exposure_category": "SIGHT:TEST-210:SIGHT:CRC",
        "factor": "0.10",
        "approval_reference": "TEST-ALCO-CRC",
    })
    approval.write_text(json.dumps(doc), encoding="utf-8")
    result = _read(reader, approval)
    assert result.approved_accounts_seen == 2
    assert len(result.reconciled_native_groups) == 2
    assert dict(result.source_native_balances) == {
        "CRC": Decimal("80"), "USD": Decimal("100")
    }
    usd = [flow for flow in result.evidence.flows if flow.currency == "USD"]
    crc = [flow for flow in result.evidence.flows if flow.currency == "CRC"]
    assert [flow.amount for flow in usd] == [Decimal("20.00"), Decimal("30.00")]
    assert len(crc) == 1 and crc[0].amount == Decimal("8.00")
    assert all(flow.area.value == "LIABILITY" for flow in result.evidence.flows)
    assert result.evidence.status == "APPROVED_SCENARIO_EVENTS_ONLY_NOT_FULL_COVERAGE"
