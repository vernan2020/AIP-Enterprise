"""Source-backed operator preflight regression; test fixtures are not AIP runtime data."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from aip.product.configured.liquidity import sugef210_operational_readiness as readiness

CUTOFF = date(2026, 9, 30)
INVENTORY = {
    "status": "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH",
    "master_review_status": "MASTER_EXACT_CUTOFF_READ",
    "xml_records_read": 114,
    "master_positions_read": 10,
}


def _configured(monkeypatch):
    monkeypatch.setenv("AIP_EXECUTION_MODE", "CONFIGURED")
    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "false")


def test_readiness_refuses_demo_without_even_reading_institutional_sources(monkeypatch):
    monkeypatch.setenv("AIP_EXECUTION_MODE", "DEMO")
    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "true")
    monkeypatch.setattr(
        readiness,
        "inspect_xml_investment_source",
        lambda cutoff: (_ for _ in ()).throw(AssertionError("Source should remain closed")),
    )
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    assert result["status"] == "BLOCKED_NOT_CONFIGURED"


def test_sources_ready_are_inventory_only_and_do_not_activate_cashflows(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    monkeypatch.setattr(
        readiness,
        "run_configured_sight_opening",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("No ALCO approvals")),
    )
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    assert result["status"] == "SOURCE_READY_APPROVALS_REQUIRED"
    assert result["xml_records_read"] == 114
    assert result["master_positions_read"] == 10
    assert result["projection_regulatorily_certified"] is False
    assert "approved_source_events" not in result


def test_master_missing_or_only_one_approval_blocks(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(
        readiness,
        "inspect_xml_investment_source",
        lambda _: {**INVENTORY, "master_review_status": "MASTER_NOT_CONFIGURED"},
    )
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    assert result["status"] == "BLOCKED_MASTER_AT_CUTOFF"

    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE", approval="approved.json")
    assert result["status"] == "BLOCKED_APPROVAL_PAIR_REQUIRED"


def test_operational_status_is_partial_with_authorized_real_source_contract(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    proxy = SimpleNamespace(
        source_name="TEST-XML-LEDGER",
        currency="CRC",
        events_inside_horizon=1,
        events_after_horizon=0,
        status="SELECTED_PAYMENTS_ONLY",
    )
    projection = SimpleNamespace(
        windows=tuple(range(17)),
        rows=tuple(
            SimpleNamespace(
                currency=currency,
                opening_liquidity=100,
            )
            for currency in ("CRC", "USD")
            for _ in range(17)
        ),
        certified_comprehensive=False,
        source_flow_count=1,
        status="PARTIAL_EVIDENCE_NOT_CERTIFIED",
        excluded_out_of_horizon=0,
    )
    received = {}

    def governed(**kwargs):
        received.update(kwargs)
        return SimpleNamespace(
            assembly=SimpleNamespace(
                projection=projection,
                audited_events=(SimpleNamespace(reference="TEST-REF"),),
                source_reconciliations=(proxy,),
                missing_institutional_evidence=("UNSELECTED_CONTRACTS",),
            )
        )

    monkeypatch.setattr(readiness, "run_configured_sight_opening", governed)
    result = readiness.evaluate_readiness(
        cutoff=CUTOFF,
        scenario="BASE",
        approval="institutional-sight.json",
        bank="institutional-bank.json",
    )
    assert result["status"] == "PARTIAL_GOVERNED_PROJECTION"
    assert result["projection_rows"] == 34
    assert result["band_count"] == 17
    assert result["approved_source_events"] == 1
    states = {row["check"]: row["state"] for row in result["operational_gates"]}
    assert states["AUTORIZACION_Y_CONCILIACION_ICL"] == "VALIDATED"
    assert states["PERIMETRO_CONTRACTUAL_INTEGRAL"] == "PARTIAL"
    assert result["opening_supported_currencies"] == ["CRC", "USD"]
    assert result["projection_regulatorily_certified"] is False
    assert "bank_or_icl_source_file" not in str(result)
    assert received["approval_manifest"] == "institutional-sight.json"
    assert received["bank_support_manifest"] == "institutional-bank.json"


def test_inconsistent_event_lineage_rejected_by_operator_preflight(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    monkeypatch.setattr(
        readiness,
        "run_configured_sight_opening",
        lambda **kwargs: SimpleNamespace(
            assembly=SimpleNamespace(
                projection=SimpleNamespace(
                    windows=tuple(range(17)),
                    rows=tuple(range(34)),
                    certified_comprehensive=False,
                    source_flow_count=1,
                ),
                audited_events=(),
            )
        ),
    )
    try:
        readiness.evaluate_readiness(
            cutoff=CUTOFF, scenario="BASE", approval="one.json", bank="two.json"
        )
    except ValueError as exc:
        assert "partial contract" in str(exc)
    else:
        raise AssertionError("Invalid institutional source count was accepted")


def test_self_test_checks_live_qt_tabs_and_never_loads_contractual_sources(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(
        readiness,
        "inspect_xml_investment_source",
        lambda *_args: (_ for _ in ()).throw(AssertionError("no institutional read")),
    )
    assert readiness.main(["--self-test"]) == 0
    result = readiness.verify_runtime_without_institutional_data()
    assert result["status"] == "RUNTIME_SELFTEST_OK"
    assert result["window_count"] == 17
    assert result["expected_currency_rows"] == 34
    assert result["institutional_files_read"] is False
    assert result["projection_regulatorily_certified"] is False


def test_self_test_refuses_source_arguments_and_demo_configuration(monkeypatch, capsys):
    import pytest

    _configured(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        readiness.main(["--self-test", "--cutoff", "2026-09-30"])
    assert exc.value.code == 2

    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "true")
    assert readiness.main(["--self-test"]) == 2
    status = capsys.readouterr().out
    assert "BLOCKED_NOT_CONFIGURED" in status


def test_source_preflight_exposes_actionable_gates_without_private_details(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    gates = {row["check"]: row for row in result["operational_gates"]}
    assert gates["XML_CONFIA_CORTE"]["state"] == "READY"
    assert gates["MAESTRO_INVERSIONES_CORTE"]["state"] == "READY"
    assert gates["AUTORIZACION_Y_CONCILIACION_ICL"]["state"] == "REQUIRED"
    assert gates["PERIMETRO_CONTRACTUAL_INTEGRAL"]["state"] == "NOT_EVALUATED"
    assert all("next_action" in row for row in gates.values())
    assert "RUTA_" not in str(result)
    assert result["projection_regulatorily_certified"] is False


def test_readiness_gates_reject_mismatched_master_and_xml(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(
        readiness,
        "inspect_xml_investment_source",
        lambda _: {
            **INVENTORY,
            "status": "BLOCKED_XML_SOURCE_UNAVAILABLE",
            "master_review_status": "MASTER_NOT_CONFIGURED",
        },
    )
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    assert result["status"] == "BLOCKED_SOURCE_INVENTORY"
    gates = {row["check"]: row["state"] for row in result["operational_gates"]}
    assert gates["XML_CONFIA_CORTE"] == "BLOCKED"
    assert gates["MAESTRO_INVERSIONES_CORTE"] == "BLOCKED"
    assert gates["AUTORIZACION_Y_CONCILIACION_ICL"] == "REQUIRED"
    assert result["projection_regulatorily_certified"] is False


def test_source_gates_before_inspection_are_pending_not_false_failures():
    gates = readiness.build_operational_gates(
        xml_status="NOT_INSPECTED",
        master_status="NOT_INSPECTED",
        approvals_provided=False,
    )
    assert [row["state"] for row in gates] == [
        "PENDING",
        "PENDING",
        "REQUIRED",
        "NOT_EVALUATED",
    ]
    assert "Inspeccionar" in gates[0]["next_action"]
    assert "Inspeccionar" in gates[1]["next_action"]


def test_rejected_approval_is_explicitly_blocked_not_pending():
    import pytest

    gates = readiness.build_operational_gates(
        xml_status="ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH",
        master_status="MASTER_EXACT_CUTOFF_READ",
        approvals_provided=True,
        approval_failed=True,
    )
    assert [row["state"] for row in gates] == [
        "READY",
        "READY",
        "BLOCKED",
        "NOT_EVALUATED",
    ]
    assert "rechazada" in gates[2]["next_action"]
    with pytest.raises(ValueError, match="Rejected authorization"):
        readiness.build_operational_gates(
            xml_status="ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH",
            master_status="MASTER_EXACT_CUTOFF_READ",
            approvals_provided=True,
            approval_failed=True,
            projection_executed=True,
        )


def test_contractual_xml_gates_expose_real_coverage_without_promoting_balances_to_cash():
    inventory = [
        {
            "source_key": "CREDIT",
            "status": "SOURCE_FIELDS_INSPECTED_NOT_A_PAYMENT_SCHEDULE",
            "records": 102560,
            "missing_balance": 12,
            "invalid_balance": 3,
            "missing_currency": 0,
            "missing_account": 2,
            "dates": [
                {
                    "field": "FechaProximoPagoPrincipal",
                    "valid": 81853,
                    "missing": 20707,
                    "invalid": 0,
                },
                {
                    "field": "FechaProximoPagoIntereses",
                    "valid": 55774,
                    "missing": 46786,
                    "invalid": 0,
                },
            ],
            "source_currency_balances_not_cashflows": {"1": "999999999999"},
            "file": "CONFIDENTIAL.xml",
        },
        {
            "source_key": "CAPTACIONES",
            "status": "SOURCE_FIELDS_INSPECTED_NOT_A_PAYMENT_SCHEDULE",
            "records": 0,
            "missing_balance": 0,
            "invalid_balance": 0,
            "missing_currency": 0,
            "missing_account": 0,
            "dates": [],
        },
        {
            "source_key": "BORROWING",
            "status": "SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO",
            "records": 0,
        },
    ]
    gates = readiness.build_contractual_source_gates(inventory)
    state = {row["check"]: row["state"] for row in gates}
    assert state == {
        "XML_CARTERA_PAGOS": "SOURCE_ONLY",
        "XML_CAPTACIONES_PAGOS": "EMPTY_REVIEW",
        "XML_OBLIGACIONES_PAGOS": "BLOCKED",
        "XML_OBLIGACIONES_BANDAS": "NOT_INSPECTED",
    }
    assert "102560 registros" in gates[0]["next_action"]
    assert "67493 fechas" in gates[0]["next_action"]
    assert "999999999999" not in str(gates)
    assert "CONFIDENTIAL.xml" not in str(gates)
    assert all(row["state"] != "READY" for row in gates)


def test_operator_preflight_includes_each_xml_contractual_perimeter_when_inspected(monkeypatch):
    _configured(monkeypatch)
    inspection = {
        **INVENTORY,
        "contractual_source_inventory": [
            {
                "source_key": "CAPTACIONES",
                "status": "SOURCE_FIELDS_INSPECTED_NOT_A_PAYMENT_SCHEDULE",
                "records": 10,
                "dates": [{"field": "FechaVencimiento", "valid": 8, "missing": 2, "invalid": 0}],
            }
        ],
    }
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: inspection)
    monkeypatch.setattr(
        readiness,
        "run_configured_sight_opening",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("Approvals required")),
    )
    outcome = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    gates = {item["check"]: item["state"] for item in outcome["operational_gates"]}
    assert outcome["status"] == "SOURCE_READY_APPROVALS_REQUIRED"
    assert gates["XML_CAPTACIONES_PAGOS"] == "SOURCE_ONLY"
    assert gates["XML_CARTERA_PAGOS"] == "NOT_INSPECTED"
    assert gates["AUTORIZACION_Y_CONCILIACION_ICL"] == "REQUIRED"
    assert outcome["projection_regulatorily_certified"] is False


def test_contractual_perimeter_inventory_rejects_duplicate_source_identity():
    import pytest

    duplicate = [
        {"source_key": "CREDIT", "status": "SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO"},
        {"source_key": "CREDIT", "status": "SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO"},
    ]
    with pytest.raises(ValueError, match="Repeated source"):
        readiness.build_contractual_source_gates(duplicate)


def test_aggregate_obligation_mapping_gates_do_not_misreport_508396_row_defects(
    monkeypatch,
):
    _configured(monkeypatch)
    mapping_review = {
        "source_key": "BORROWING_MATURITY",
        "status": "AGGREGATE_SOURCE_FIELD_MAP_REVIEW_REQUIRED",
        "records": 254198,
        "missing_balance": 254198,
        "missing_account": 254198,
        "unmapped_source_fields": [
            "SaldoaPagarPrincipal",
            "CuentaContablePrincipal",
        ],
        "observed_xml_tag_names": ["MontoBandaOriginal", "TipoRangoPasivo"],
        "source_currency_balances_not_cashflows": {"1": "SENSITIVE"},
    }
    monkeypatch.setattr(
        readiness,
        "inspect_xml_investment_source",
        lambda _: {**INVENTORY, "contractual_source_inventory": [mapping_review]},
    )
    report = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    gates = {row["check"]: row for row in report["operational_gates"]}
    band = gates["XML_OBLIGACIONES_BANDAS"]
    assert band["state"] == "SCHEMA_REVIEW"
    assert "254198 registros" in band["next_action"]
    assert "508396" not in str(report)
    assert "SENSITIVE" not in str(report)
    assert report["aggregate_obligation_xml_schema"]["expected_tags_not_observed"] == [
        "SaldoaPagarPrincipal",
        "CuentaContablePrincipal",
    ]
    assert report["aggregate_obligation_xml_schema"]["observed_tag_names_only"] == [
        "MontoBandaOriginal",
        "TipoRangoPasivo",
    ]
    assert report["projection_regulatorily_certified"] is False


def test_aggregate_obligation_tags_present_remain_reference_only():
    status = {
        "source_key": "BORROWING_MATURITY",
        "status": "AGGREGATE_SOURCE_REFERENCE_NOT_CASHFLOWS",
        "records": 254198,
        "unmapped_source_fields": [],
    }
    item = readiness.build_contractual_source_gates([status])[-1]
    assert item["state"] == "REFERENCE_ONLY"
    assert "calendario de liquidación" in item["next_action"]


def test_identity_linkage_is_opt_in_and_never_recognizes_cashflows(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    calls = []

    def inspect(cutoff):
        calls.append(cutoff)
        return {
            "status": "MATCHED_REFERENCE_ONLY",
            "unique_maturity_rows_matched": 28,
            "ambiguous_maturity_rows": 3,
            "cashflows_recognized": 0,
        }

    monkeypatch.setattr(readiness, "inspect_obligation_identity_with_config", inspect)
    ordinary = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    assert calls == []
    assert "obligation_identity_linkage" not in ordinary

    enriched = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE", identity_linkage=True)
    assert calls == [CUTOFF]
    assert enriched["status"] == "SOURCE_READY_APPROVALS_REQUIRED"
    assert enriched["projection_regulatorily_certified"] is False
    assert enriched["obligation_identity_linkage"]["cashflows_recognized"] == 0
    matching_gate = next(
        row
        for row in enriched["operational_gates"]
        if row["check"] == "XML_OBLIGACIONES_VINCULACION"
    )
    assert matching_gate["state"] == "REFERENCE_ONLY"
    assert "28" in matching_gate["next_action"]


def test_linkage_mismatch_not_reported_as_ready(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    monkeypatch.setattr(
        readiness,
        "inspect_obligation_identity_with_config",
        lambda _: {"status": "BLOCKED_SOURCE_HEADER_MISMATCH", "cashflows_recognized": 0},
    )
    output = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE", identity_linkage=True)
    matching_gate = next(
        row for row in output["operational_gates"] if row["check"] == "XML_OBLIGACIONES_VINCULACION"
    )
    assert matching_gate["state"] == "REVIEW_REQUIRED"
    assert output["projection_regulatorily_certified"] is False
