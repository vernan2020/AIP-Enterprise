from __future__ import annotations

import json
import subprocess
from datetime import date

from scripts.qa.run_readonly_rtilb_validation import CHECKS, _safe_status, execute_suite


def test_only_known_source_evidence_statuses_are_accepted() -> None:
    assert _safe_status('{"status": "VALIDATED", "private_id": "SECRET"}') == "VALIDATED"
    assert _safe_status('{"status": "CERTIFIED", "private_id": "SECRET"}') == "NOT_CONFIRMED"
    assert _safe_status("path=SECRET\\nnot-json") == "NOT_CONFIRMED"


def test_global_suite_runs_each_configured_diagnostic_with_same_cutoff(
    tmp_path, monkeypatch
) -> None:
    for _, name in CHECKS:
        (tmp_path / name).write_text("@echo off", encoding="utf-8")
    statuses = (
        "LOCAL_SOURCE_PREFLIGHT_ONLY",
        "VALIDATED",
        "COVERAGE_INSPECTED",
        "AGGREGATE_GAPS_INSPECTED",
        "AGGREGATE_EXPOSURE_AUDITED",
        "MATURITY_EVIDENCE_ONLY_NOT_IRRBB_GAP",
        "INVESTMENT_MASTER_SOURCE_INSPECTED_NOT_CERTIFIED",
    )
    called = []

    def fake_run(arguments, **kwargs):
        called.append(arguments)
        return subprocess.CompletedProcess(
            arguments, 0, json.dumps({"status": statuses[len(called) - 1], "secret": "SECRET"}), ""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    report = execute_suite(tmp_path, date(2026, 9, 30))
    assert report["all_diagnostics_passed"] is True
    assert report["certified_gap_19"] is False
    assert report["financial_modules_certified"] is False
    assert len(called) == len(CHECKS)
    assert all(args[-1] == "2026-09-30" for args in called)
    assert "SECRET" not in json.dumps(report)
    assert all(entry["result"] == "PASSED_EVIDENCE_ONLY" for entry in report["checks"])


def test_nonzero_or_missing_diagnostic_remains_blocked(tmp_path, monkeypatch) -> None:
    (tmp_path / CHECKS[0][1]).write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 2, '{"status": "VALIDATED"}', ""),
    )
    report = execute_suite(tmp_path, date(2026, 9, 30))
    assert report["all_diagnostics_passed"] is False
    assert report["checks"][0]["result"] == "BLOCKED"
    assert report["checks"][1]["result"] == "MISSING_DIAGNOSTIC"
